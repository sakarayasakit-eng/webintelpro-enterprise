import yaml
from pathlib import Path


class Config:
    def __init__(self):
        self.file = Path("config.yaml")

        if not self.file.exists() or self.file.stat().st_size == 0:
            self.create_default()

        with open(self.file, "r", encoding="utf-8") as f:
            self.data = yaml.safe_load(f)

    def create_default(self):
        default = {
            "project": {
                "name": "WebIntelPro Enterprise X",
                "version": "1.0"
            },
            "crawler": {
                "timeout": 20,
                "max_pages": 100,
                "user_agent": "WebIntelPro Enterprise X"
            },
            "reports": {
                "output": "reports"
            }
        }

        with open(self.file, "w", encoding="utf-8") as f:
            yaml.dump(default, f, sort_keys=False)

    def get(self, section, key=None):
        if key is None:
            return self.data.get(section, {})
        return self.data.get(section, {}).get(key)