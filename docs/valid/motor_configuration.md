---
title: "Brushless Motor & Inverter Configuration Parameters"
description: "Specification guide for configuring motor pole pairs, torque constant (Kt), current limits, and thermal protection boundaries."
category: "Hardware Configuration"
firmware_version: "v0.5.6"
status: "production"
last_reviewed: "2026-08-14"
tags: ["motor", "kv-rating", "torque-constant", "current-limits", "hardware"]
---

# Brushless Motor & Inverter Configuration Parameters

Accurate motor configuration is critical for stable Field-Oriented Control (FOC). Incorrect electrical parameters degrade current regulation bandwidth and can induce rotor instability or thermal runaway.

---

## Fundamental Electrical Parameters

Set these motor specifications in `odrv0.axis0.motor.config` prior to initiating the electrical calibration routine.

### Pole Pairs and KV Rating

The pole pair count represents the number of permanent magnet pole pairs on the rotor (total rotor magnets divided by two).

```python
# Configure a 14-pole rotor (7 pole pairs)
odrv0.axis0.motor.config.pole_pairs = 7

# Set the motor type to high-current gimbal or standard BLDC
from odrive.enums import MOTOR_TYPE_HIGH_CURRENT
odrv0.axis0.motor.config.motor_type = MOTOR_TYPE_HIGH_CURRENT
```

### Torque Constant Calculation

ODrive calculates motor torque directly from the quadrature current ($I_q$) using the torque constant $K_t$ (in $\text{N}\cdot\text{m}/\text{A}$). Calculate $K_t$ from the motor velocity constant $K_v$ (in $\text{RPM}/\text{V}$):

$$K_t = \frac{8.27}{K_v}$$

For example, a motor rated at $270\text{ KV}$:

$$K_t = \frac{8.27}{270} \approx 0.03063\text{ N}\cdot\text{m}/\text{A}$$

```python
odrv0.axis0.motor.config.torque_constant = 8.27 / 270.0
```

---

## Current and Safety Boundaries

Protect your inverter MOSFETs and motor windings by setting strict current limits.

### Calibration and Inverter Current Limits

| Parameter Path | Unit | Default | Description |
| :--- | :--- | :--- | :--- |
| `motor.config.calibration_current` | $\text{A}$ | $10.0$ | DC test current applied during resistance/inductance measurement. |
| `motor.config.current_lim` | $\text{A}$ | $10.0$ | Maximum continuous phase current during closed-loop operation. |
| `motor.config.current_lim_margin` | $\text{A}$ | $8.0$ | Current overshoot headroom before triggering `ERROR_CURRENT_LIMIT_VIOLATION`. |
| `motor.config.resistance_calib_max_voltage` | $\text{V}$ | $2.0$ | Maximum voltage applied to reach calibration current. |

```python
# Set continuous current limit to 25 Amps with 10A calibration current
odrv0.axis0.motor.config.calibration_current = 10.0
odrv0.axis0.motor.config.current_lim = 25.0
odrv0.axis0.motor.config.current_lim_margin = 8.0
odrv0.axis0.motor.config.resistance_calib_max_voltage = 4.0
```

---

## Thermal Protection and Throttling

ODrive includes on-board thermistor inputs to throttle phase current automatically when operating near thermal limits.

### Thermistor Configuration

Configure the thermistor coefficient and upper cutoff temperature:

```python
# Enable thermistor monitoring for Axis 0
odrv0.axis0.motor.config.thermistor_enable = True
odrv0.axis0.motor.config.temperature_limit_lower = 80.0  # Begins linear throttling at 80°C
odrv0.axis0.motor.config.temperature_limit_upper = 100.0 # Shuts down drive at 100°C
```

---

## Persistence and Verification

Verify parameters and persist to flash memory:

```python
odrv0.save_configuration()
print("Motor parameters successfully written to non-volatile storage.")
```
