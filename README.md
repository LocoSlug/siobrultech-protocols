![Lint](https://github.com/sdwilsh/siobrultech-protocols/workflows/Lint/badge.svg)
![Build](https://github.com/sdwilsh/siobrultech-protocols/workflows/Build/badge.svg)

# What is siobrultech-protocols?

This library is a collection of protcols that decode various packet formats from
[Brultech Research](https://www.brultech.com/).

# What is Sans-I/O?

Sans-I/O is a philosophy for developing protocol processing libraries in which
the library does not do any I/O. Instead, a user of the library is responsible
for transferring blocks of bytes between the socket or pipe and the protocol
library, and for receiving application-level protocol items from and sending
them to the library. This obviously makes a sans-I/O library a little more
difficult to use, but comes with the advantage that the same library can be
used with any I/O and concurrency mechanism: the same library should be usable
in a single-request-at-a-time server, a process-per-request or
thread-per-request blocking server, a server using select/poll and
continuations, or a server using asyncio, Twisted, or any other asynchronous
framework.

See [SansIO](https://sans-io.readthedocs.io/) for more information.

## Installation

```
pip install siobrultech-protocols
```

## Usage

### Receiving data packets

```python
import functools
from siobrultech_protocols.gem.protocol import PacketProtocol, PacketReceivedMessage

# Queue to get received packets from.
queue = asyncio.Queue()

# Pass this Protocol to whatever receives data from the device.
protocol_factory = functools.partial(PacketProtocol, queue=queue)

# Dequeue and look for packet received messages. (Typically do this in a loop.)
message = await queue.get()
if isinstance(message, PacketReceivedMessage):
    packet = message.packet
queue.task_done()
```

### Receiving data packets AND sending API commands

If you want to send API commands as well, use a `BidirectionalProtocol` instead of a `PacketProtocol`. Then given the `protocol` instance for a given connection, do the API call as follows:

```python
from siobrultech_protocols.gem.api import get_serial_number

serial = await get_serial_number(protocol)
```

`siobrultech_protocols` provides direct support for a small set of API calls. Some of these calls work for both GEM and ECM monitors, others are GEM-only.

#### Methods to Get Information from a Device

| Method              | GEM | ECM | Description                              |
| ------------------- | --- | --- | ---------------------------------------- |
| `get_serial_number` |  ✅︎  |  ✅︎ | Obtains the serial number of the device. |

#### Methods to Setup a Device

| Method                        | GEM | ECM | Description                                                                 |
| ----------------------------- | --- | --- | --------------------------------------------------------------------------- |
| `set_date_and_time`           |  ✅︎  |  ❌  | Sets the GEM's clock to the specified `datetime`.                           |
| `set_packet_format`           |  ✅︎  |  ❌  | Sets the GEM's packet format to the specified `PacketFormatType`.           |
| `set_packet_send_interval`    |  ✅︎  |  ✅︎  | Sets the frequency (seconds) that the monitor should send packets.              |
| `set_secondary_packet_format` |  ✅︎  |  ❌  | Sets the GEM's secondary packet format to the specified `PacketFormatType`. |
| `synchronize_time`            |  ✅︎  |  ❌  | Synchronizes the GEM's clock to the time of the local device.               |

### Calling API endpoints that aren't supported by this library

`siobrultech_protocols` has built-in support for just a tiny subset of the full API exposed by GEM and ECM. If you want to call an API endpoint for which this library doesn't provide a helper, you can make your own. For example, the following outline could be filled in to support the "get all settings" endpoint; you could define `GET_ALL_SETTINGS`:

```python
from siobrultech_protocols.gem import api

# Define a Python data type for the response. It can be whatever you want; a simple Dict, a custom dataclass, etc.
AllSettings = Dict[str, Any]

def _parse_all_gem_settings(response: str) -> AllSettings:
    # Here you would parse the GEM response into the python type you defined above

def _parse_all_ecm_settings(response: bytes) -> AllSettings:
    # Here you would parse the ECM response into the python type you defined above

GET_ALL_SETTINGS = api.ApiCall[None, AllSettings](
    gem_formatter=lambda _: "^^^RQSALL", gem_parser=_parse_all_gem_settings,
    ecm_formatter=lambda _: [b"\xfc", b"SET", b"RCV"], ecm_parser=_parse_all_ecm_settings,
)
```

Given an `ApiCall` (whether one of those in `siobrultech_protocols.api` or defined yourself as above), you can
make the request by working with the protocol directly as follows:

```python
# Start the API request; do this once for each API call. Each protocol instance can only support one
# API call at a time.
delay = protocol.begin_api_request()
sleep(delay)  # Wait for the specified delay, using whatever mechanism is appropriate for your environment

# Send the API request. We use asyncio's implementation of Future, but you can use whatever you like.
result = asyncio.get_event_loop().create_future()
protocol.invoke_api(GET_ALL_SETTINGS, None, result)
settings = await asyncio.wait_for(result, timeout=5)

# End the API request
protocol.end_api_request()
```

Alternatively, we also provide a context wrapper that works with `asyncio` as well:

```python
from siobrultech_protocols.gem import api

async with api.call_api(GET_ALL_SETTINGS, protocol) as f:
    settings = await f(None)
```

Take a look at some usage examples from [libraries that use this](https://github.com/sdwilsh/siobrultech-protocols/network/dependents).

### Calling API endpoints when multiple devices share a connection

All of the API helper methods take an optional `serial_number` parameter to target a specific device if there are multiple devices on the same connection. This has no effect for ECM devices.

## Development

### Setup

```
python3.11 -m venv .venv
source .venv/bin/activate

# Install Requirements
pip install -r requirements.txt

# Install Dev Requirements
pip install -r requirements-dev.txt
```

### Testing

Tests are run with `pytest`.

### Linting

Lint can be run with [Earthly](https://earthly.dev/) with `./earthly.sh +lint`
