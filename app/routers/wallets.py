import os

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.demo_wallets import get_demo_enriched_data
from app.models import Wallet
from app.schemas import (
    DeleteWalletResponse,
    WalletBalanceResponse,
    WalletIngestRequest,
    WalletIngestResponse,
    WalletReputationResponse,
    WalletResponse,
    WalletTransfersResponse,
)
from app.services.blockchain import (
    get_asset_transfers_for_wallet,
    get_latest_block_number,
    get_wallet_balance,
)
from app.services.job_queue import JobQueue, get_job_queue

router = APIRouter(
    prefix="/wallets",
    tags=["wallets"],
)


def is_valid_eth_address(address: str) -> bool:
    return (
        isinstance(address, str)
        and address.startswith("0x")
        and len(address) == 42
    )


def normalize_address(address: str) -> str:
    return address.lower()


def wallet_to_response(wallet: Wallet) -> WalletResponse:
    return WalletResponse(
        id=wallet.id,
        address=wallet.wallet_address,
        source=wallet.source,
        last_seen_block=wallet.last_seen_block,
        created_at=wallet.created_at,
    )


def get_wallet_or_404(wallet_address: str, db: Session) -> Wallet:
    address = normalize_address(wallet_address)

    wallet = (
        db.query(Wallet)
        .filter(Wallet.wallet_address == address)
        .first()
    )

    if not wallet:
        raise HTTPException(status_code=404, detail="Wallet not found")

    return wallet


def _demo_mode_enabled() -> bool:
    return os.getenv(
        "DEMO_MODE",
        "false",
    ).strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


def calculate_wallet_reputation(
    address: str,
    max_count: int = 10,
) -> WalletReputationResponse:
    """
    Calculate reputation using either synthetic demo fixtures or
    the existing live blockchain provider.
    """
    demo_data = None

    if _demo_mode_enabled():
        demo_data = get_demo_enriched_data(address)

    if demo_data is not None:
        balance = {
            "balance_eth": demo_data["balance"],
            "network": "synthetic-demo",
        }

        transfer_status = demo_data.get(
            "source_status",
            {},
        ).get(
            "transfers",
            "available",
        )

        transfer_error = demo_data.get(
            "errors",
            {},
        ).get("transfers")

        if transfer_status == "unavailable":
            transfers = []
        else:
            transfers = demo_data.get(
                "transfers",
                [],
            )[:max_count]
    else:
        balance = get_wallet_balance(address)

        transfers = []
        transfer_status = "available"
        transfer_error = None

        try:
            transfers = get_asset_transfers_for_wallet(
                address,
                max_count=max_count,
            )
        except Exception as exc:
            transfer_status = "unavailable"
            transfer_error = str(exc)

    balance_eth = float(balance["balance_eth"])
    transfer_count = len(transfers)

    score = 0

    if balance_eth > 0:
        score += 25

    if balance_eth >= 0.01:
        score += 15

    if transfer_status in {"available", "partial"}:
        if transfer_count >= 1:
            score += 25

        if transfer_count >= 5:
            score += 20

        if transfer_count >= 10:
            score += 15
    else:
        score += 10

    score = min(score, 100)

    if score >= 80:
        level = "high"
    elif score >= 50:
        level = "medium"
    else:
        level = "low"

    if transfer_status == "unavailable":
        note = (
            "Partial score used because transfer data "
            "was unavailable."
        )
    elif transfer_status == "partial":
        note = "Score uses partial transfer data."
    elif demo_data is not None:
        note = "Synthetic demo score used."
    else:
        note = "Full score used."

    return WalletReputationResponse(
        address=address,
        score=score,
        level=level,
        signals={
            "balance_eth": balance["balance_eth"],
            "transfer_count": transfer_count,
            "transfer_status": transfer_status,
            "transfer_error": transfer_error,
            "network": balance["network"],
            "note": note,
        },
    )



def queue_wallet_rescore(
    queue: JobQueue,
    address: str,
) -> tuple[str, bool]:
    from app.routers.jobs import submit_scoring_job

    return submit_scoring_job(
        queue,
        address,
        refresh=True,
    )


@router.post(
    "/ingest",
    response_model=WalletIngestResponse,
    summary="Ingest or refresh a wallet",
    description=(
        "Stores a normalized wallet address and its latest observed block. "
        "An existing wallet is refreshed without creating a duplicate."
    ),
)
def ingest_wallet(
    payload: WalletIngestRequest,
    db: Session = Depends(get_db),
    queue: JobQueue = Depends(get_job_queue),
):
    address = normalize_address(payload.address)

    if not is_valid_eth_address(address):
        raise HTTPException(
            status_code=400,
            detail=(
                "Invalid Ethereum wallet address. "
                "Address must start with 0x and be 42 characters long."
            ),
        )

    try:
        latest_block = get_latest_block_number()
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch latest block from Alchemy: {str(exc)}",
        ) from exc

    existing_wallet = (
        db.query(Wallet)
        .filter(Wallet.wallet_address == address)
        .first()
    )

    if existing_wallet:
        previous_block = existing_wallet.last_seen_block
        existing_wallet.last_seen_block = latest_block
        db.commit()
        db.refresh(existing_wallet)

        if previous_block != latest_block:
            queue_wallet_rescore(
                queue,
                existing_wallet.wallet_address,
            )

        return WalletIngestResponse(
            status="already_exists",
            address=existing_wallet.wallet_address,
            last_seen_block=existing_wallet.last_seen_block,
        )

    new_wallet = Wallet(
        wallet_address=address,
        source="alchemy",
        last_seen_block=latest_block,
    )

    db.add(new_wallet)
    db.commit()
    db.refresh(new_wallet)

    queue_wallet_rescore(
        queue,
        new_wallet.wallet_address,
    )

    return WalletIngestResponse(
        status="ingested",
        address=new_wallet.wallet_address,
        last_seen_block=new_wallet.last_seen_block,
    )


@router.get(
    "",
    response_model=list[WalletResponse],
    summary="List ingested wallets",
)
def list_wallets(db: Session = Depends(get_db)):
    wallets = db.query(Wallet).order_by(Wallet.id.desc()).all()
    return [wallet_to_response(wallet) for wallet in wallets]


@router.get(
    "/{wallet_address}",
    response_model=WalletResponse,
    summary="Get an ingested wallet",
)
def get_wallet(
    wallet_address: str,
    db: Session = Depends(get_db),
):
    wallet = get_wallet_or_404(wallet_address, db)
    return wallet_to_response(wallet)


@router.delete(
    "/{wallet_address}",
    response_model=DeleteWalletResponse,
    summary="Delete an ingested wallet",
)
def delete_wallet(
    wallet_address: str,
    db: Session = Depends(get_db),
):
    wallet = get_wallet_or_404(wallet_address, db)

    db.delete(wallet)
    db.commit()

    return {
        "status": "deleted",
        "address": wallet.wallet_address,
    }


@router.get(
    "/{wallet_address}/balance",
    response_model=WalletBalanceResponse,
    summary="Get a wallet balance",
)
def get_wallet_balance_route(wallet_address: str):
    address = normalize_address(wallet_address)

    if not is_valid_eth_address(address):
        raise HTTPException(
            status_code=400,
            detail="Invalid Ethereum wallet address",
        )

    try:
        return get_wallet_balance(address)
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch wallet balance: {str(exc)}",
        ) from exc


@router.get(
    "/{wallet_address}/transfers",
    response_model=WalletTransfersResponse,
    summary="Get recent wallet transfers",
    description="Returns between one and 50 recent asset transfers.",
)
def get_wallet_transfers_route(
    wallet_address: str,
    max_count: int = 10,
):
    address = normalize_address(wallet_address)

    if not is_valid_eth_address(address):
        raise HTTPException(
            status_code=400,
            detail="Invalid Ethereum wallet address",
        )

    if max_count < 1 or max_count > 50:
        raise HTTPException(
            status_code=400,
            detail="max_count must be between 1 and 50",
        )

    try:
        transfers = get_asset_transfers_for_wallet(
            address,
            max_count=max_count,
        )
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch wallet transfers: {str(exc)}",
        ) from exc

    return WalletTransfersResponse(
        address=address,
        count=len(transfers),
        transfers=transfers,
    )


@router.get(
    "/{wallet_address}/reputation",
    response_model=WalletReputationResponse,
    summary="Get the base wallet reputation",
    description=(
        "Calculates the cumulative Week 2 reputation score from balance "
        "and recent transfer signals."
    ),
)
def get_wallet_reputation_route(
    wallet_address: str,
    max_count: int = 10,
):
    address = normalize_address(wallet_address)

    if not is_valid_eth_address(address):
        raise HTTPException(
            status_code=400,
            detail="Invalid Ethereum wallet address",
        )

    if max_count < 1 or max_count > 50:
        raise HTTPException(
            status_code=400,
            detail="max_count must be between 1 and 50",
        )

    try:
        return calculate_wallet_reputation(
            address,
            max_count=max_count,
        )
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch wallet balance: {str(exc)}",
        ) from exc
