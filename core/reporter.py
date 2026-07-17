import json
from pathlib import Path
from datetime import datetime


class Reporter:

    def __init__(self):

        self.output = Path("reports")
        self.output.mkdir(exist_ok=True)

    def save(self, report):

        filename = (
            "report_"
            + datetime.now().strftime("%Y%m%d_%H%M%S")
            + ".json"
        )

        filepath = self.output / filename

        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=4)

        print(f"\nReport saved to:\n{filepath}")