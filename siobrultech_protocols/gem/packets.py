"""
Packet formats defined in
https://www.brultech.com/software/files/downloadSoft/GEM-PKT_Packet_Format_2_1.pdf
"""
from __future__ import annotations

import codecs
import json
from collections import OrderedDict
from datetime import datetime
from typing import Any, Dict, List, Optional

from .fields import (
    ByteField,
    BytesField,
    DateTimeField,
    Field,
    FloatingPointArrayField,
    FloatingPointField,
    NumericArrayField,
    NumericField,
    hi_to_lo,
    lo_to_hi,
    lo_to_hi_signed,
)


class MalformedPacketException(Exception):
    pass


class Packet(object):
    def __init__(
        self,
        packet_format: PacketFormat,
        voltage: float,
        absolute_watt_seconds: List[int],
        device_id: int,
        serial_number: int,
        seconds: int,
        pulse_counts: List[int],
        temperatures: List[float],
        polarized_watt_seconds: Optional[List[int]] = None,
        currents: Optional[List[float]] = None,
        time_stamp: Optional[datetime] = None,
        **kwargs: Dict[str, Any]
    ):
        self.packet_format: PacketFormat = packet_format
        self.voltage: float = voltage
        self.absolute_watt_seconds: List[int] = absolute_watt_seconds
        self.polarized_watt_seconds: Optional[List[int]] = polarized_watt_seconds
        self.currents: Optional[List[float]] = currents
        self.device_id: int = device_id
        self.serial_number: int = serial_number
        self.seconds: int = seconds
        self.pulse_counts: List[int] = pulse_counts
        self.temperatures: List[float] = temperatures
        if time_stamp:
            self.time_stamp: datetime = time_stamp
        else:
            self.time_stamp: datetime = datetime.now()

    def __str__(self) -> str:
        return json.dumps(
            {
                "device_id": self.device_id,
                "serial_number": self.serial_number,
                "seconds": self.seconds,
                "voltage": self.voltage,
                "absolute_watt_seconds": self.absolute_watt_seconds,
                "polarized_watt_seconds": self.polarized_watt_seconds,
                "currents": self.currents,
                "pulse_counts": self.pulse_counts,
                "temperatures": self.temperatures,
                "time_stamp": self.time_stamp.isoformat(),
            }
        )

    @property
    def type(self) -> str:
        return self.packet_format.name

    @property
    def num_channels(self) -> int:
        return self.packet_format.num_channels

    @property
    def max_seconds(self) -> int:
        assert isinstance(self.packet_format.fields["seconds"], NumericField)
        return self.packet_format.fields["seconds"].max

    @property
    def max_pulse_count(self) -> int:
        assert isinstance(self.packet_format.fields["pulse_counts"], NumericArrayField)
        return self.packet_format.fields["pulse_counts"].elem_field.max

    @property
    def max_absolute_watt_seconds(self) -> int:
        assert isinstance(
            self.packet_format.fields["absolute_watt_seconds"], NumericArrayField
        )
        return self.packet_format.fields["absolute_watt_seconds"].elem_field.max

    @property
    def max_polarized_watt_seconds(self) -> int:
        assert isinstance(
            self.packet_format.fields["polarized_watt_seconds"], NumericArrayField
        )
        return self.packet_format.fields["polarized_watt_seconds"].elem_field.max


class PacketFormat(object):
    NUM_PULSE_COUNTERS: int = 4
    NUM_TEMPERATURE_SENSORS: int = 8

    def __init__(
        self,
        name: str,
        num_channels: int,
        has_net_metering: bool = False,
        has_time_stamp: bool = False,
    ):
        self.name: str = name
        self.num_channels: int = num_channels
        self.fields: OrderedDict[str, Field] = OrderedDict()

        self.fields["header"] = NumericField(3, hi_to_lo)
        self.fields["voltage"] = FloatingPointField(2, hi_to_lo, 10.0)
        self.fields["absolute_watt_seconds"] = NumericArrayField(
            num_channels, 5, lo_to_hi
        )
        if has_net_metering:
            self.fields["polarized_watt_seconds"] = NumericArrayField(
                num_channels, 5, lo_to_hi
            )
        self.fields["serial_number"] = NumericField(2, hi_to_lo)
        self.fields["reserved"] = ByteField()
        self.fields["device_id"] = NumericField(1, hi_to_lo)
        self.fields["currents"] = FloatingPointArrayField(
            num_channels, 2, lo_to_hi, 50.0
        )
        self.fields["seconds"] = NumericField(3, lo_to_hi)
        self.fields["pulse_counts"] = NumericArrayField(
            PacketFormat.NUM_PULSE_COUNTERS, 3, lo_to_hi
        )
        self.fields["temperatures"] = FloatingPointArrayField(
            PacketFormat.NUM_TEMPERATURE_SENSORS,
            2,
            lo_to_hi_signed,
            2.0,
        )
        if num_channels == 32:
            self.fields["spare_bytes"] = BytesField(2)
        if has_time_stamp:
            self.fields["time_stamp"] = DateTimeField()
        self.fields["footer"] = NumericField(2, hi_to_lo)
        self.fields["checksum"] = ByteField()

    @property
    def size(self) -> int:
        result = 0
        for value in self.fields.values():
            result += value.size

        return result

    def parse(self, packet: bytes) -> Packet:
        if len(packet) < self.size:
            raise MalformedPacketException(
                "Packet too short. Expected {0} bytes, found {1} bytes.".format(
                    self.size, len(packet)
                )
            )
        _checksum(packet, self.size)

        offset = 0
        args = {
            "packet_format": self,
        }
        for key, value in self.fields.items():
            args[key] = value.read(packet, offset)
            offset += value.size

        if args["footer"] != 0xFFFE:
            raise MalformedPacketException(
                "bad footer {0} in packet: {1}".format(
                    hex(args["footer"]), codecs.encode(packet, "hex")  # type: ignore
                )
            )

        return Packet(**args)  # type: ignore


def _checksum(packet: bytes, size: int):
    checksum = 0
    for i in packet[: size - 1]:
        checksum += i
    checksum = checksum % 256
    if checksum != packet[size - 1]:
        raise MalformedPacketException(
            "bad checksum for packet: {0}".format(codecs.encode(packet[:size], "hex"))
        )


BIN48_NET_TIME = PacketFormat(
    name="BIN48-NET-TIME", num_channels=48, has_net_metering=True, has_time_stamp=True
)

BIN48_NET = PacketFormat(
    name="BIN48-NET", num_channels=48, has_net_metering=True, has_time_stamp=False
)

BIN48_ABS = PacketFormat(
    name="BIN48-ABS", num_channels=48, has_net_metering=False, has_time_stamp=False
)

BIN32_NET = PacketFormat(
    name="BIN32-NET", num_channels=32, has_net_metering=True, has_time_stamp=False
)

BIN32_ABS = PacketFormat(
    name="BIN32-ABS", num_channels=32, has_net_metering=False, has_time_stamp=False
)
