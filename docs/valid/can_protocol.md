---
title: "CAN Simple Protocol & Telemetry Interface"
description: "Specification for CAN 2.0B communication with ODrive controllers, message arbitration ID architecture, and cyclic telemetry configuration."
category: "Communication Protocols"
firmware_version: "v0.5.6"
status: "production"
last_reviewed: "2026-08-14"
tags: ["can-bus", "can-simple", "telemetry", "embedded", "robotics"]
---

# CAN Simple Protocol & Telemetry Interface

The ODrive CAN Simple Protocol operates over standard CAN 2.0B (11-bit arbitration IDs) at configurable baud rates up to 1 Mbps. It enables high-bandwidth deterministic control between a host controller and multiple secondary ODrive target nodes on a shared multidrop bus.

---

## CAN Arbitration ID Architecture

The 11-bit standard CAN ID is partitioned into two distinct bitfields: the **Node ID** (6 bits) and the **Command ID** (5 bits).

$$\text{CAN ID} = (\text{Node ID} \ll 5) \mid \text{Command ID}$$

```text
 10   9   8   7   6   5   4   3   2   1   0  (Bit Position)
+---+---+---+---+---+---+---+---+---+---+---+
|       Node ID (6 bits)|   Command ID (5)  |
+---+---+---+---+---+---+---+---+---+---+---+
```

### Standard Command Identifiers

| Command Name | Command ID (Hex) | Direction | Payload Length | Description |
| :--- | :--- | :--- | :--- | :--- |
| `CANOPEN_NMT` | `0x000` | Host $\to$ Target | 2 Bytes | Network management broadcast. |
| `ODRIVE_HEARTBEAT` | `0x001` | Target $\to$ Host | 8 Bytes | Transmits `axis_error`, `current_state`, and controller flags. |
| `SET_AXIS_NODE_ID` | `0x006` | Host $\to$ Target | 4 Bytes | Dynamically reassigns node arbitration address. |
| `SET_AXIS_REQUESTED_STATE` | `0x007` | Host $\to$ Target | 4 Bytes | Requests state transition (e.g., closed loop). |
| `GET_ENCODER_ESTIMATES` | `0x009` | Target $\to$ Host | 8 Bytes | Returns position and velocity floating-point estimates. |
| `SET_INPUT_POS` | `0x00C` | Host $\to$ Target | 8 Bytes | Sends target position with velocity and torque feedforward. |
| `SET_INPUT_VEL` | `0x00D` | Host $\to$ Target | 8 Bytes | Sends velocity setpoint and torque feedforward. |
| `SET_INPUT_TORQUE` | `0x00E` | Host $\to$ Target | 4 Bytes | Sends direct motor torque target in $\text{N}\cdot\text{m}$. |

---

## Cyclic Telemetry Configuration

To eliminate command-response polling latency over the bus, configure cyclic telemetry broadcasts.

### Configuring Periodic Heartbeat and Feedback

Enable automatic cyclic broadcasts on Axis 0 with specific intervals:

```python
# Set Node ID to 0x01
odrv0.axis0.config.can.node_id = 1

# Configure CAN baud rate to 500 kbps (500000)
odrv0.can.config.baud_rate = 500000

# Enable cyclic heartbeat message at 100 Hz (10 ms period)
odrv0.axis0.config.can.heartbeat_rate_ms = 10

# Enable encoder position and velocity cyclic feedback at 200 Hz (5 ms period)
odrv0.axis0.config.can.encoder_rate_ms = 5

# Persist and reboot to apply baud rate changes
odrv0.save_configuration()
odrv0.reboot()
```

---

## Python SocketCAN Integration Example

Control the axis via Linux SocketCAN (`can0` interface) using `python-can`:

```python
import struct
import can

# Initialize SocketCAN bus connection
bus = can.Bus(channel='can0', interface='socketcan', bitrate=500000)

NODE_ID = 0x01
CMD_SET_INPUT_POS = 0x00C
can_id = (NODE_ID << 5) | CMD_SET_INPUT_POS

# Target position = 10.0 turns, vel_ff = 0, torque_ff = 0
position_turns = 10.0
vel_ff = 0.0
torque_ff = 0.0

# Pack binary payload (float32, int16, int16)
data = struct.pack('<fhh', position_turns, int(vel_ff * 1000), int(torque_ff * 1000))

msg = can.Message(
    arbitration_id=can_id,
    data=data,
    is_extended_id=False
)

bus.send(msg)
print(f"Dispatched CAN position frame: 0x{can_id:03X}")
```
