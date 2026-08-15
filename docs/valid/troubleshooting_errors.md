---
title: "ODrive Error Reference, Root Cause Analysis & Community Diagnostics"
description: "Comprehensive diagnostics catalog mapping hardware error bitfields, root causes, and community-verified solutions from ODrive engineering forums."
category: "Diagnostics & Troubleshooting"
firmware_version: "v0.5.6"
status: "production"
last_reviewed: "2026-08-14"
tags: ["troubleshooting", "error-codes", "drv-fault", "overvoltage", "calibration-error"]
---

# ODrive Error Reference, Root Cause Analysis & Community Diagnostics

When an ODrive encounters an electrical fault, physical constraint, or protocol violation, the controller immediately disengages closed-loop control and latches error flags in the active register bank.

---

## Critical System & Axis Error Catalog

The table below catalogs high-frequency errors, their hardware root causes, and community-verified remediation protocols. Every enum name and value below is verified against the official [ODriveArduino](https://github.com/odriverobotics/ODriveArduino) library (`ODriveEnums.h`, v0.10.9) — current firmware reports these across three distinct enums rather than one flat bitfield, so pick the right table for the symptom you're seeing.

### Hardware & Electrical Errors (`ODrive.Error` bitfield — `odrv0.axis0.active_errors`)

| Error Enum | Bitfield Value | Underlying Cause | Community-Verified Remediation |
| :--- | :--- | :--- | :--- |
| `ODRIVE_ERROR_DRV_FAULT` | `0x00000020` | Gate driver fault (short circuit, VDS overcurrent, or supply dip). | Inspect phase motor solder joints for shorts; ensure motor cables are separated from low-voltage encoder wiring. |
| `ODRIVE_ERROR_DC_BUS_OVER_VOLTAGE` | `0x00000100` | Regenerative braking energy returned to DC bus without dissipation path. | Connect a $50\text{W}$ $2\Omega$ power brake resistor and set `odrv0.config.enable_brake_resistor = True`. |
| `ODRIVE_ERROR_DC_BUS_OVER_CURRENT` | `0x00000400` | DC bus current exceeded the configured hardware limit, often from a shorted phase or undersized supply. | Check motor phase wiring for shorts; verify `config.dc_max_positive_current` matches supply capability. |
| `ODRIVE_ERROR_CURRENT_LIMIT_VIOLATION` | `0x00001000` | Commanded current exceeded `motor.config.current_lim`. | Reduce `controller.config.vel_gain`, or raise `current_lim` if the motor and inverter can safely handle more current. |

### Calibration Procedure Failures (`ODrive.ProcedureResult` — `odrv0.axis0.procedure_result`)

These are **not** bitfield errors — a calibration sequence returns exactly one `ProcedureResult` value on completion.

| Result Enum | Integer Value | Underlying Cause | Community-Verified Remediation |
| :--- | :--- | :--- | :--- |
| `PROCEDURE_RESULT_PHASE_RESISTANCE_OUT_OF_RANGE` | `6` | Measured resistance exceeds bounds or motor phase disconnected during calibration. | Verify all three motor bullet connectors; increase `resistance_calib_max_voltage` from $2.0\text{V}$ to $4.0\text{V}$ for high-resistance windings. |
| `PROCEDURE_RESULT_PHASE_INDUCTANCE_OUT_OF_RANGE` | `7` | Measured inductance is out of expected physical bounds ($10^{-6}$ to $10^{-3}\text{ H}$). | Ensure the motor shaft is free to spin during electrical measurement; check phase wire continuity. |
| `PROCEDURE_RESULT_POLE_PAIR_CPR_MISMATCH` | `5` | Calibrated count delta does not match expected electrical angle counts per revolution. | Recalculate physical rotor pole pairs ($N_{\text{magnets}} / 2$) and ensure mechanical coupling has zero backlash. |

### Sensor & Encoder Errors (`ODrive.ComponentStatus` — `odrv0.axis0.encoder.status`)

| Status Enum | Integer Value | Underlying Cause | Community-Verified Remediation |
| :--- | :--- | :--- | :--- |
| `COMPONENT_STATUS_INDEX_NOT_FOUND` | `12` | Encoder configured with `use_index = True` but index pulse was not detected during search sweep. | Verify encoder CPR setting in `encoder.config.cpr`; check shielding on index line (`Z` pin). |

> **Note:** older ODrive documentation referenced a standalone `ERROR_UNSTABLE_GAIN` flag. It has no equivalent in the current library — velocity estimator jitter from an overly aggressive PLL bandwidth no longer raises a dedicated flag, so tune it proactively by decreasing `encoder.config.bandwidth` from the default $1000$ to $500\text{ rad/s}$ if you observe noisy velocity feedback.

---

## Community-Sourced Troubleshooting Playbooks

These step-by-step diagnostic workflows address the most frequently discussed failure modes on the ODrive Discourse community.

### Playbook 1: Resolving `ProcedureResult.DISARM_ERROR` and `NOT_CALIBRATED`

#### Symptom
The axis refuses to enter `AXIS_STATE_CLOSED_LOOP_CONTROL`, immediately dropping back to `AXIS_STATE_IDLE` with `PROCEDURE_RESULT_DISARMED` (`3`) or `PROCEDURE_RESULT_NOT_CALIBRATED` (`14`).

#### Step-by-Step Resolution
1. Run the error dump utility to isolate the sub-module:
   ```python
   import odrive
   from odrive.utils import dump_errors
   odrv0 = odrive.find_any()
   dump_errors(odrv0)
   ```
2. Verify that mechanical rotor calibration succeeded without motor resistance errors.
3. Confirm that `is_calibrated` flags evaluate to `True`:
   ```python
   print("Motor Calibrated:", odrv0.axis0.motor.is_calibrated)
   print("Encoder Calibrated:", odrv0.axis0.encoder.is_ready)
   ```
4. If calibration is valid, persist settings to flash memory before issuing closed-loop commands:
   ```python
   odrv0.axis0.motor.config.pre_calibrated = True
   odrv0.axis0.encoder.config.pre_calibrated = True
   odrv0.save_configuration()
   ```

### Playbook 2: Eliminating High-Speed DRV Faults Under Acceleration

#### Symptom
The drive operates smoothly at low speeds, but trips `ERROR_DRV_FAULT` during rapid velocity reversal or high acceleration steps.

#### Step-by-Step Resolution
1. Set the brake resistor resistance value accurately in software:
   ```python
   odrv0.config.brake_resistance = 2.0
   odrv0.config.enable_brake_resistor = True
   ```
2. Increase the DC bus overvoltage threshold margin slightly above nominal supply voltage:
   ```python
   odrv0.config.dc_bus_overvoltage_trip_level = 56.0  # For 48V power supplies
   ```
3. Add a low-pass filter to the current setpoint or reduce `controller.config.vel_gain` to prevent current overshoot spikes.
