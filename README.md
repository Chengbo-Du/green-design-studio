# GDS - Green Design Studio

Building performance simulation system bridging EnergyPlus/CONTAM with Grasshopper/Rhino.

## Repository Structure

```
gds/
├── gds/                    # Core Python library (pip installable)
│   ├── presets/            # HVAC, schedule, renewable presets
│   ├── parsers/            # GDS JSON database parsers
│   ├── models/             # Data models (GDSProgramData, etc.)
│   └── utils/              # GH helpers, geometry utilities
├── grasshopper/            # Grasshopper components
│   ├── GDS_Hub.py          # Building definition UI (v63)
│   └── GDS_Refiner.py      # Assembly modification UI (v8)
├── setup.py                # pip install configuration
└── README.md
```

## Installation

### For Users

```bash
# Install core library
pip install git+https://github.com/Chengbo-Du/gds.git

# Then copy GDS_Hub.py and GDS_Refiner.py into GhPython components
```

### For Development

```bash
git clone https://github.com/Chengbo-Du/gds.git
cd gds
pip install -e .
```

## Usage in Grasshopper

1. Create a GhPython component
2. Copy contents of `grasshopper/GDS_Hub.py`
3. Rename input to `RUN`
4. Connect a Button

## Components

| Component | Version | Description |
|-----------|---------|-------------|
| GDS Hub | v63 | Building definition control panel |
| GDS Refiner | v8 | Assembly modification tool |

## Version

- **gds-core**: 0.1.0
- **GDS Hub**: v63
- **GDS Refiner**: v8

## Author

Chengbo Du - Syracuse University

## License

MIT License
