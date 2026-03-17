# FORIOT 18650 Battery Holder / Power Bank Module Data Sheet

## Product Overview

The FORIOT 18650 Battery Holder is a dual-compartment Li-ion battery power bank module with Micro USB charging and USB/expansion port output. It provides a complete solution for building a portable power supply using standard 18650 batteries.

![Product Top View](./images/Screenshot%20from%202026-03-16%2021-53-15.png)

![Product Side View](./images/Screenshot%20from%202026-03-16%2021-54-08.png)

![Product Label View](./images/Screenshot%20from%202026-03-16%2022-01-24.png)

---

## Key Features

- Dual 18650 battery compartment (parallel configuration)
- Micro USB input for charging (5V/3A)
- Dual output options: USB-A port and expansion pins
- 5-level LED power indicator
- Built-in lithium battery protection IC
- Power on/off control switch
- Up to 95% conversion efficiency
- Over-current, over-voltage, under-voltage, and over-temperature protection

---

## Technical Specifications

### Electrical Specifications

| Parameter | Value |
|-----------|-------|
| Input Port | Micro USB |
| Input Voltage | 5V DC |
| Input Current | 3A (recommended 5V/1A or higher charger) |
| Output Port 1 | USB-A (5V/3A or 3V/1A) |
| Output Port 2 | Expansion header pins |
| Conversion Efficiency | Up to 95% |

### Battery Specifications

| Parameter | Value |
|-----------|-------|
| Battery Type | 18650 Li-ion |
| Number of Cells | 2 (parallel) |
| Battery Voltage Range | 3.2V - 4.2V |
| Maximum Output Current | 3A |
| Charging Current | 1.5A |

### Protection Features

| Protection | Description |
|------------|-------------|
| Over-current Protection | Yes |
| Over-voltage Protection | Yes |
| Under-voltage Protection | Yes |
| Over-temperature Protection | Yes |

### Environmental Specifications

| Parameter | Value |
|-----------|-------|
| Operating Temperature | -20°C to 70°C |
| Storage Temperature | -40°C to 85°C |

---

## Physical Specifications

| Parameter | Value |
|-----------|-------|
| PCB Dimensions | 99.16mm × 29.28mm × 21mm (L × W × H) |
| Package Dimensions | 142mm × 76mm × 22mm |
| Weight | 33g (1.16 oz) |

---

## Pinout & Interface

### Expansion Port Pinout

| Pin Number | Function |
|------------|----------|
| 1 | BAT+ (Battery Positive) |
| 2 | BAT- (Battery Negative) |
| 3 | USB D+ (Data+) |
| 4 | USB D- (Data-) |
| 5 | OUT+ (Output Positive) |
| 6 | OUT- (Output Negative) |

### Micro USB Port

- Used for charging the 18650 batteries
- Requires 5V/1A or higher power adapter

### USB-A Output Port

- Provides 5V/3A or 3V/1A output
- Can be used to power external devices

---

## LED Indicator Guide

### Charging Mode

| Battery Level | LED Status |
|---------------|------------|
| 100% | All 5 LEDs lit |
| 80-99% | D5 blinking |
| 60-80% | D4 blinking |
| 40-60% | D3 blinking |
| 20-40% | D2 blinking |
| 0-20% | D1 blinking |

### Discharge Mode

| Battery Level | LED Status |
|---------------|------------|
| 80-100% | All 5 LEDs lit |
| 60-80% | D5 off |
| 40-60% | D4, D5 off |
| 20-40% | D3, D4, D5 off |
| 5-20% | D2, D3, D4, D5 off |
| 1-5% | D1 blinking |
| 0% | All LEDs off |

---

## Operation Instructions

### Power On/Off

1. **Power On**: Press the power button to turn on
2. **Power Off**: Press and hold the button for 3 seconds to shut down
3. **Auto Mode**: Toggle switch for auto-on or manual on/off mode

### Charging

1. Connect Micro USB cable to the input port
2. Connect USB power adapter (5V/1A or higher recommended)
3. LED indicators show charging progress
4. Automatically stops charging when batteries are full

### Discharging

1. Press power button to enable output
2. Connect device via USB-A port or expansion pins
3. LED indicators show remaining battery capacity
4. Press and hold button for 3 seconds to turn off

---

## Wiring Diagram

```
                    ┌─────────────────────┐
                    │    18650 Battery    │
                    │       Holder        │
                    │  ┌─────┐  ┌─────┐   │
                    │  │ B1  │  │ B2  │   │
                    │  │     │  │     │   │
                    │  │ +   │  │ +   │   │
                    │  │ -   │  │ -   │   │
                    │  └─────┘  └─────┘   │
                    │      │       │      │
                    │      └───────┘      │
                    │         │           │
                    └─────────┼───────────┘
                              │
                    ┌─────────┴─────────┐
                    │   Protection IC   │
                    │   (IP5306/MT4089) │
                    └─────────┬─────────┘
                              │
         ┌────────────────────┼────────────────────┐
         │                    │                    │
         ▼                    ▼                    ▼
   ┌───────────┐      ┌──────────────┐    ┌──────────────┐
   │ Micro USB │      │   USB-A      │    │  Expansion   │
   │   Input   │      │   Output     │    │    Pins      │
   │ 5V/3A     │      │  5V/3A       │    │   (VCC/GND)  │
   └───────────┘      └──────────────┘    └──────────────┘
```

---

## Dimensions (mm)

```
   ┌──────────────────────────────────────────────────┐
   │  99.16mm                                        │
   │◄───────────────────────────────────────────────►│
   │  ┌──────────────────────────────────────────┐   │
   │  │ ┌────┐ ┌────┐   ┌──┐ ┌──┐ ┌──┐ ┌──┐    │   │ 29.28mm
   │  │ │Batt│ │Batt│   │SW│ │LED│ │USB│ │MICRO│  │◄►
   │  │ │ 1  │ │ 2  │   │  │ │ 5 │ │ A │ │ USB │  │
   │  │ └────┘ └────┘   └──┘ └──┘ └──┘ └──┘    │   │
   │  └──────────────────────────────────────────┘   │
   │                      21mm                       │
   └──────────────────────────────────────────────────┘
```

---

## Model Variants

| Model | Configuration | Output |
|-------|---------------|--------|
| B0CJR1Y967 | 1-Holder (2pcs) | 5V/2A |
| **B0CJQZ2CLS** | **2-Holder (Dual)** | **5V/3A / 3V/1A** |
| B0DLGSGNS5 | 4-Holder | 5V/3A / 3V/1A |

---

## Applications

- Portable power bank
- Raspberry Pi / Arduino power supply
- DIY electronics projects
- IoT device power backup
- Emergency lighting
- Mobile device charging
- Outdoor/remote power solutions

---

## Usage Notes

1. **Battery Installation**: Insert 18650 batteries with correct polarity (+/-)
2. **Parallel Only**: Do NOT connect batteries in series - this increases voltage and may damage the module
3. **For Higher Capacity**: Connect batteries in parallel to increase mAh capacity
4. **Recommended Charger**: Use 5V/1A or higher USB power adapter for charging
5. **Heat Dissipation**: Ensure adequate ventilation during high-current operation

---

## Package Contents

- 1 × FORIOT 18650 Battery Holder Module (Dual Compartment)
- 1 × Micro USB Charging Cable

---

## Ordering Information

| Item | Value |
|------|-------|
| Brand | FORIOT |
| Model | A42_GXHB0002-001_US |
| ASIN | B0CJQZ2CLS |
| Date Available | September 25, 2023 |
| Price | $11.99 |

---

## Typical Connection for Raspberry Pi

```
┌────────────────────────────┐
│   FORIOT 18650 Module      │
│                            │
│   ┌────┐ ┌────┐            │
│   │Batt│ │Batt│            │
│   │ 1  │ │ 2  │            │
│   └────┘ └────┘            │
│        │                  │
│   [USB-A] ────► 5V Power   │
│                            │
│   Expansion:               │
│   OUT+ ────► 5V Pin        │
│   OUT- ────► GND Pin       │
└────────────────────────────┘
         │
         ▼
┌────────────────────────────┐
│     Raspberry Pi            │
│     (USB Micro-B)          │
└────────────────────────────┘
```

---

**Document Version:** 1.0  
**Date:** March 2026  
**Source:** Amazon Product Page (ASIN: B0CJQZ2CLS)
