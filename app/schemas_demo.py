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
    model_config = ConfigDict(extra="forbid")

    demo_mode_enabled: bool
    wallets: list[DemoWalletSummary]
