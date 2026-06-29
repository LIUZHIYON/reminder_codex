#!/bin/bash
# Audio setup for speaker on boot
amixer sset 'spk switch' on
amixer sset 'Speaker' on
amixer sset 'aw_dev_0_switch' Enable
amixer sset 'aw_dev_0_rx_volume' 1023
amixer sset 'aw_dev_0_prof' Music
amixer sset 'Headphone' off
