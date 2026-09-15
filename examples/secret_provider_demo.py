"""Host-injected skill credentials without mutating os.environ."""

import os

from skillware.core.loader import SkillLoader
from skillware.core.secrets import MappingSecretProvider

os.environ.pop("ETHERSCAN_API_KEY", None)

bundle = SkillLoader.load_skill("finance/wallet_screening")
provider = MappingSecretProvider({"ETHERSCAN_API_KEY": "demo-host-injected-key"})
config = SkillLoader.resolve_env_vars(bundle["manifest"], provider)
skill = bundle["class"](config=config)

assert skill.etherscan_api_key == "demo-host-injected-key"
print("Host-injected ETHERSCAN_API_KEY accepted via config (no os.environ).")
