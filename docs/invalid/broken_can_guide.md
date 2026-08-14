---
title: "Legacy CAN Setup Guide"
description: "An unreviewed draft guide for setting up CAN networks."
category: "Communication Protocols"
status: "draft"
last_reviewed: "invalid-date-format"
---

# Legacy CAN Setup Guide

This guide describes how to connect ODrive to a CAN bus.

### Quick Setup

It is very easy to use the CAN bus. You simply connect the CAN high and CAN low wires, and obviously everything will work right away. Just connect your controller to the node.

In this setup, the PC acts as the master-slave controller. We also maintain a blacklist of node IDs that should not be contacted on the bus, alongside a whitelist of approved devices.

To see the complete configuration parameters, [click here](http://localhost:9999/broken-link-sample).

```
# Untagged code block without language
odrv0.axis0.config.can.node_id = 0x01
odrv0.can.config.baud_rate = 250000
```

For more information, please note that the motor calibration should be performed before the system is commanded into closed loop control by the operator.
