"""
IFF binary parser for The Sims 1 Neighborhood.iff files.

Parses NBRS (neighbour/sim data), FAMI (family definitions), and FAMs
(family names in STR format) chunks from the IFF container format.
"""

from __future__ import annotations

import struct
from dataclasses import dataclass, field
from pathlib import Path


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class Personality:
    nice: int = 0
    active: int = 0
    playful: int = 0
    outgoing: int = 0
    neat: int = 0


@dataclass
class Interests:
    travel: int = 0    # adults: Travel, children: Toys
    violence: int = 0  # adults: Violence, children: Aliens
    politics: int = 0  # adults: Politics, children: Pets
    sixties: int = 0   # adults: 60s/70s, children: School
    weather: int = 0
    sports: int = 0
    music: int = 0
    outdoors: int = 0


@dataclass
class Sim:
    id: int  # neighbour_id
    guid: int
    name: str
    age: str  # "child" or "adult"
    gender: str  # "male" or "female"
    family_number: int
    personality: Personality = field(default_factory=Personality)
    interests: Interests = field(default_factory=Interests)


@dataclass
class Family:
    chunk_id: int  # IFF chunk ID, used to match with FAMs
    family_number: int  # in-game family number
    name: str
    house_number: int
    budget: int
    member_guids: list[int] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Low-level IFF chunk reader
# ---------------------------------------------------------------------------

def _read_chunks(data: bytes) -> list[tuple[str, int, bytes]]:
    """
    Parse all chunks from an IFF file.
    Returns a list of (chunk_type, chunk_id, chunk_data) tuples.
    """
    # 60-byte ASCII header + 4-byte resource map offset
    pos = 64
    chunks: list[tuple[str, int, bytes]] = []

    while pos < len(data):
        if pos + 76 > len(data):
            break

        # Chunk header is big-endian
        chunk_type = data[pos:pos + 4].decode("ascii", errors="replace")
        chunk_size = struct.unpack_from(">I", data, pos + 4)[0]
        chunk_id = struct.unpack_from(">H", data, pos + 8)[0]
        # flags at pos+10 (2 bytes), label at pos+12 (64 bytes) -- skipped

        if chunk_size < 76:
            # Malformed chunk, skip forward
            pos += 76
            continue

        chunk_data = data[pos + 76 : pos + chunk_size]
        chunks.append((chunk_type, chunk_id, chunk_data))

        pos += chunk_size

    return chunks


# ---------------------------------------------------------------------------
# String reader helper
# ---------------------------------------------------------------------------

def _read_null_terminated_string(data: bytes, offset: int) -> tuple[str, int]:
    """
    Read a null-terminated string from *data* starting at *offset*.
    Returns (string_value, new_offset_after_null_byte).
    """
    end = data.index(b"\x00", offset)
    value = data[offset:end].decode("ascii", errors="replace")
    return value, end + 1  # skip past the null terminator


# ---------------------------------------------------------------------------
# NBRS chunk parser
# ---------------------------------------------------------------------------

INTEREST_INDICES = [46, 47, 48, 49, 50, 51, 52, 53]
INTEREST_NAMES = [
    "travel", "violence", "politics", "sixties",
    "weather", "sports", "music", "outdoors",
]


def _parse_nbrs(data: bytes) -> list[Sim]:
    """Parse an NBRS chunk and return a list of Sim objects."""
    sims: list[Sim] = []
    pos = 0

    # Header: 4B pad + 4B version + 4B magic + 4B count
    _pad, version, magic_raw, count = struct.unpack_from("<I I 4s I", data, pos)
    pos += 16

    magic = magic_raw.decode("ascii", errors="replace")
    if magic != "SRBN":
        return sims

    for _ in range(count):
        entry_start = pos

        # unknown1 must be 1 for a valid entry
        unknown1 = struct.unpack_from("<i", data, pos)[0]
        pos += 4
        if unknown1 != 1:
            # Skip this entry -- we cannot know its size, so bail out.
            break

        # version per neighbour
        nbr_version = struct.unpack_from("<i", data, pos)[0]
        pos += 4

        # If version == 0xA, there is an extra int32
        if nbr_version == 0xA:
            _unknown3 = struct.unpack_from("<i", data, pos)[0]
            pos += 4

        # Null-terminated name
        name, pos = _read_null_terminated_string(data, pos)

        # Padding: if len(name) is even (including the null byte the total
        # written bytes would be odd), skip one extra byte to align.
        # The rule from the spec: if len(name) % 2 == 0, skip extra padding byte.
        if len(name) % 2 == 0:
            pos += 1

        # mystery_zero (i32)
        _mystery_zero = struct.unpack_from("<i", data, pos)[0]
        pos += 4

        # person_mode (i32)
        person_mode = struct.unpack_from("<i", data, pos)[0]
        pos += 4

        person_data_shorts: list[int] = []
        if person_mode > 0:
            # PersonData: padded to a fixed size depending on version
            if nbr_version == 0xA:
                person_data_size = 0x200  # 512 bytes
            else:
                person_data_size = 0xA0  # 160 bytes

            # Read 88 shorts (176 bytes) -- the meaningful portion
            num_shorts = min(88, person_data_size // 2)
            person_data_shorts = list(
                struct.unpack_from(f"<{num_shorts}h", data, pos)
            )

            pos += person_data_size

        # neighbour_id (i16)
        neighbour_id = struct.unpack_from("<h", data, pos)[0]
        pos += 2

        # guid (u32)
        guid = struct.unpack_from("<I", data, pos)[0]
        pos += 4

        # unknown_neg_one (i32)
        _unknown_neg_one = struct.unpack_from("<i", data, pos)[0]
        pos += 4

        # relationship_count (i32)
        rel_count = struct.unpack_from("<i", data, pos)[0]
        pos += 4

        # Relationships
        for _ in range(rel_count):
            key_count = struct.unpack_from("<i", data, pos)[0]
            pos += 4
            # keys
            pos += 4 * key_count
            value_count = struct.unpack_from("<i", data, pos)[0]
            pos += 4
            # values
            pos += 4 * value_count

        # Only keep sims that have PersonData
        if person_mode <= 0 or len(person_data_shorts) < 88:
            continue

        # -- Extract personality -----------------------------------------------
        personality = Personality(
            nice=person_data_shorts[2],
            active=person_data_shorts[3],
            playful=person_data_shorts[5],
            outgoing=person_data_shorts[6],
            neat=person_data_shorts[7],
        )

        # -- Extract interests -------------------------------------------------
        raw_interests = [person_data_shorts[i] for i in INTEREST_INDICES]

        # Normalize: if max interest value <= 10, multiply all by 100
        max_interest = max(raw_interests) if raw_interests else 0
        if max_interest <= 10:
            raw_interests = [v * 100 for v in raw_interests]

        interests = Interests(
            travel=raw_interests[0],
            violence=raw_interests[1],
            politics=raw_interests[2],
            sixties=raw_interests[3],
            weather=raw_interests[4],
            sports=raw_interests[5],
            music=raw_interests[6],
            outdoors=raw_interests[7],
        )

        # -- Age & gender ------------------------------------------------------
        persons_age = person_data_shorts[58]
        age = "child" if persons_age < 18 else "adult"

        gender_val = person_data_shorts[65]
        gender = "female" if gender_val == 1 else "male"

        family_number = person_data_shorts[61]

        sim = Sim(
            id=neighbour_id,
            guid=guid,
            name=name,
            age=age,
            gender=gender,
            family_number=family_number,
            personality=personality,
            interests=interests,
        )
        sims.append(sim)

    return sims


# ---------------------------------------------------------------------------
# FAMI chunk parser
# ---------------------------------------------------------------------------

def _parse_fami(data: bytes, chunk_id: int) -> Family | None:
    """Parse a single FAMI chunk and return a Family object."""
    if len(data) < 40:
        return None

    pos = 0
    _pad, version, magic_raw = struct.unpack_from("<I I 4s", data, pos)
    pos += 12

    magic = magic_raw.decode("ascii", errors="replace")
    if magic != "IMAF":
        return None

    house_number, family_number, budget = struct.unpack_from("<i i i", data, pos)
    pos += 12

    _value_arch, _family_friends, _flags = struct.unpack_from("<i i i", data, pos)
    pos += 12

    guid_count = struct.unpack_from("<i", data, pos)[0]
    pos += 4

    guids: list[int] = []
    for _ in range(guid_count):
        g = struct.unpack_from("<I", data, pos)[0]
        pos += 4
        guids.append(g)

    return Family(
        chunk_id=chunk_id,
        family_number=family_number,
        name="",  # will be filled from FAMs
        house_number=house_number,
        budget=budget,
        member_guids=guids,
    )


# ---------------------------------------------------------------------------
# FAMs chunk parser (STR format -3 / 0xFFFD)
# ---------------------------------------------------------------------------

def _parse_fams(data: bytes) -> str:
    """
    Parse a FAMs chunk (STR# format code -3) and return the first string
    value, which is the family name.
    """
    if len(data) < 4:
        return ""

    format_code, string_count = struct.unpack_from("<h H", data, 0)
    pos = 4

    if format_code != -3 or string_count == 0:
        return ""

    # Read the first string entry: 1 byte lang_code + null-terminated value + null-terminated comment
    _lang_code = data[pos]
    pos += 1

    value, pos = _read_null_terminated_string(data, pos)
    # comment follows (null-terminated) -- we skip it
    return value


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def parse_neighborhood(userdata_path: str) -> tuple[list[Sim], list[Family]]:
    """
    Parse `Neighborhood.iff` from the given UserData directory path.

    Returns (sims, families) where each sim has person data populated and
    each family has its name resolved from the corresponding FAMs chunk.
    """
    iff_path = Path(userdata_path) / "Neighborhood.iff"
    data = iff_path.read_bytes()

    chunks = _read_chunks(data)

    sims: list[Sim] = []
    families: list[Family] = []
    family_names: dict[int, str] = {}  # chunk_id -> name

    # First pass: collect all chunks
    for chunk_type, chunk_id, chunk_data in chunks:
        if chunk_type == "NBRS":
            sims.extend(_parse_nbrs(chunk_data))
        elif chunk_type == "FAMI":
            fam = _parse_fami(chunk_data, chunk_id)
            if fam is not None:
                families.append(fam)
        elif chunk_type == "FAMs":
            name = _parse_fams(chunk_data)
            if name:
                family_names[chunk_id] = name

    # Match family names by chunk ID (FAMs chunk_id == FAMI chunk_id)
    for family in families:
        if family.chunk_id in family_names:
            family.name = family_names[family.chunk_id]

    # Build guid -> family lookup from member_guids
    guid_to_family: dict[int, Family] = {}
    for family in families:
        for guid in family.member_guids:
            guid_to_family[guid] = family

    # Assign family info to sims by GUID
    for sim in sims:
        family = guid_to_family.get(sim.guid)
        if family:
            sim.family_number = family.chunk_id

    return sims, families
