from fastapi import APIRouter

router = APIRouter(
    prefix="/wallets",
    tags=["Wallets"]
)

@router.get("/")
def test_wallet_route():
    return {
        "message": "Wallet route is working"
    }