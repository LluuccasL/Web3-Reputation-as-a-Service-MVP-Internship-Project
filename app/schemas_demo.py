from pydantic import BaseModel, ConfigDict

from app.schemas import WalletAddress


class DemoWalletSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    scenario_key: str
    address: WalletAddress
    label: str
    description: str
    expected_outcome: str
    synthetic: bool
    group_id: str | None = None


class DemoWalletCatalogResponse(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={
            "example": {
                "demo_mode_enabled": True,
                "wallets": [
                    {
                        "scenario_key": "established_human",
                        "address": (
                            "0xd000000000000000000000000000000000000001"
                        ),
                        "label": "Established human wallet",
                        "description": (
                            "Long lifespan with varied counterparties."
                        ),
                        "expected_outcome": (
                            "Positive score factors and a likely Gold tier."
                        ),
                        "synthetic": True,
                        "group_id": None,
                    }
                ],
            }
        },
    )

    demo_mode_enabled: bool
    wallets: list[DemoWalletSummary]
