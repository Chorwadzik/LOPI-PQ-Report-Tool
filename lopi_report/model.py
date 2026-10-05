from dataclasses import dataclass, field
from datetime import datetime
import math


@dataclass
class Dataset:
    times: list[datetime]
    channels: dict[str, list[float | None]]
    units: dict[str, str]
    metadata: dict = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)
    source_files: list[str] = field(default_factory=list)

    def validate(self):
        if not self.times or not self.channels:
            raise ValueError('Brak danych pomiarowych do raportu.')
        if any(b <= a for a, b in zip(self.times, self.times[1:])):
            raise ValueError('Znaczniki czasu muszą być rosnące i unikalne.')
        for name, values in self.channels.items():
            if len(values) != len(self.times):
                raise ValueError(f'Niezgodna liczba próbek kanału {name}.')
            if any(v is not None and not math.isfinite(v) for v in values):
                raise ValueError(f'Nieskończona lub nieprawidłowa wartość w {name}.')
        return self

    def subset(self, names):
        return Dataset(self.times, {k: self.channels[k] for k in names},
                       {k: self.units.get(k, '') for k in names},
                       dict(self.metadata), list(self.warnings), list(self.source_files)).validate()
