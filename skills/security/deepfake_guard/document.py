"""Document structure, geometry, and ICAO 9303 MRZ checksum validation."""

from __future__ import annotations

import datetime
from typing import Any, Dict, List, Optional, Tuple, Union

from PIL import Image

try:
    from .constants import (
        ASPECT_RATIO_TD1,
        ASPECT_RATIO_TD2,
        ASPECT_RATIO_TD3,
        ASPECT_RATIO_TOLERANCE,
        ICAO_WEIGHTS,
    )
except (ImportError, ValueError):
    import os
    import sys

    _pkg_dir = os.path.dirname(os.path.abspath(__file__))
    if _pkg_dir not in sys.path:
        sys.path.insert(0, _pkg_dir)
    from constants import (
        ASPECT_RATIO_TD1,
        ASPECT_RATIO_TD2,
        ASPECT_RATIO_TD3,
        ASPECT_RATIO_TOLERANCE,
        ICAO_WEIGHTS,
    )


def _char_value(c: str) -> int:
    """ICAO 9303 character values: '<' = 0, '0'-'9' = 0-9, 'A'-'Z' = 10-35."""
    if c == "<":
        return 0
    if "0" <= c <= "9":
        return ord(c) - ord("0")
    if "A" <= c <= "Z":
        return ord(c) - ord("A") + 10
    if "a" <= c <= "z":
        return ord(c) - ord("a") + 10
    return 0


def calculate_icao_check_digit(data: str) -> int:
    """
    Computes ICAO 9303 check digit using cyclical weights (7, 3, 1).
    """
    total = 0
    for idx, char in enumerate(data):
        weight = ICAO_WEIGHTS[idx % 3]
        total += _char_value(char) * weight
    return total % 10


def _parse_yy_mm_dd(date_str: str) -> Tuple[Optional[datetime.date], bool]:
    """Parses 6-digit YYMMDD date string into date object and returns (date, is_expired)."""
    if len(date_str) != 6 or not date_str.isdigit():
        return None, False

    yy = int(date_str[0:2])
    mm = int(date_str[2:4])
    dd = int(date_str[4:6])

    if mm < 1 or mm > 12 or dd < 1 or dd > 31:
        return None, False

    # Current century heuristic: if YY <= current_year % 100 + 10, treat as 20YY, else 19YY
    now = datetime.datetime.now(datetime.timezone.utc).date()
    current_yy = now.year % 100

    year = 2000 + yy if yy <= (current_yy + 15) else 1900 + yy

    try:
        parsed_date = datetime.date(year, mm, dd)
        is_expired = parsed_date < now
        return parsed_date, is_expired
    except ValueError:
        return None, False


def parse_and_validate_mrz(raw_mrz: Union[str, List[str]]) -> Dict[str, Any]:
    """
    Parses and cryptographically validates ICAO 9303 MRZ strings across
    TD1 (3x30), TD2 (2x36), and TD3 (2x44) travel document formats.
    """
    if isinstance(raw_mrz, str):
        # Split on newline or strip
        lines = [
            line.strip().upper()
            for line in raw_mrz.strip().splitlines()
            if line.strip()
        ]
    else:
        lines = [str(line).strip().upper() for line in raw_mrz if str(line).strip()]

    # If single contiguous block without newlines, attempt slicing by standard lengths
    if len(lines) == 1:
        single = lines[0]
        if len(single) == 88:
            lines = [single[0:44], single[44:88]]
        elif len(single) == 90:
            lines = [single[0:30], single[30:60], single[60:90]]
        elif len(single) == 72:
            lines = [single[0:36], single[36:72]]

    num_lines = len(lines)
    if num_lines not in (2, 3):
        return {
            "format": "unknown",
            "mrz_valid": False,
            "checksum_failures": ["invalid_line_count"],
            "fields": {},
            "error": f"Invalid MRZ line count: expected 2 or 3 lines, got {num_lines}.",
        }

    line_lens = [len(item) for item in lines]
    checksum_failures: List[str] = []
    fields: Dict[str, Any] = {}

    # -------------------------------------------------------------------------
    # Format: TD3 (Passport - 2 lines of 44 chars)
    # -------------------------------------------------------------------------
    if num_lines == 2 and line_lens[0] == 44 and line_lens[1] == 44:
        doc_format = "TD3"
        l1, l2 = lines[0], lines[1]

        doc_type = l1[0:2].replace("<", "")
        issuer_country = l1[2:5].replace("<", "")
        name_segment = l1[5:44]
        name_parts = name_segment.split("<<", 1)
        surname = name_parts[0].replace("<", " ").strip()
        given_names = (
            name_parts[1].replace("<", " ").strip() if len(name_parts) > 1 else ""
        )

        doc_number_raw = l2[0:9]
        doc_number = doc_number_raw.replace("<", "")
        doc_num_cd_claimed = l2[9]

        nationality = l2[10:13].replace("<", "")
        dob_raw = l2[13:19]
        dob_cd_claimed = l2[19]

        sex = l2[20]
        expiry_raw = l2[21:27]
        expiry_cd_claimed = l2[27]

        personal_num_raw = l2[28:42]
        personal_num = personal_num_raw.replace("<", "")
        personal_cd_claimed = l2[42]

        composite_cd_claimed = l2[43]

        # 1. Document number check digit
        doc_num_cd_calc = calculate_icao_check_digit(doc_number_raw)
        if (
            not doc_num_cd_claimed.isdigit()
            or int(doc_num_cd_claimed) != doc_num_cd_calc
        ):
            checksum_failures.append("document_number_checksum")

        # 2. Date of birth check digit
        dob_cd_calc = calculate_icao_check_digit(dob_raw)
        if not dob_cd_claimed.isdigit() or int(dob_cd_claimed) != dob_cd_calc:
            checksum_failures.append("date_of_birth_checksum")

        # 3. Expiry date check digit
        expiry_cd_calc = calculate_icao_check_digit(expiry_raw)
        if not expiry_cd_claimed.isdigit() or int(expiry_cd_claimed) != expiry_cd_calc:
            checksum_failures.append("expiry_date_checksum")

        # 4. Optional personal number check digit (if present and not '<')
        if personal_cd_claimed != "<":
            personal_cd_calc = calculate_icao_check_digit(personal_num_raw)
            if (
                not personal_cd_claimed.isdigit()
                or int(personal_cd_claimed) != personal_cd_calc
            ):
                checksum_failures.append("personal_number_checksum")

        # 5. Composite check digit: calculated over l2[0:10] + l2[13:20] + l2[21:43]
        composite_data = l2[0:10] + l2[13:20] + l2[21:43]
        composite_cd_calc = calculate_icao_check_digit(composite_data)
        if (
            not composite_cd_claimed.isdigit()
            or int(composite_cd_claimed) != composite_cd_calc
        ):
            checksum_failures.append("composite_checksum")

        _, is_expired = _parse_yy_mm_dd(expiry_raw)

        fields = {
            "document_type": doc_type or "P",
            "issuer": issuer_country,
            "document_number": doc_number,
            "surname": surname,
            "given_names": given_names,
            "nationality": nationality,
            "date_of_birth": dob_raw,
            "sex": sex if sex in ("M", "F", "X") else "X",
            "expiry_date": expiry_raw,
            "is_expired": is_expired,
            "personal_number": personal_num,
        }

    # -------------------------------------------------------------------------
    # Format: TD1 (National ID Card - 3 lines of 30 chars)
    # -------------------------------------------------------------------------
    elif (
        num_lines == 3
        and line_lens[0] == 30
        and line_lens[1] == 30
        and line_lens[2] == 30
    ):
        doc_format = "TD1"
        l1, l2, l3 = lines[0], lines[1], lines[2]

        doc_type = l1[0:2].replace("<", "")
        issuer_country = l1[2:5].replace("<", "")
        doc_number_raw = l1[5:14]
        doc_number = doc_number_raw.replace("<", "")
        doc_num_cd_claimed = l1[14]

        # Line 2: DOB (6), CD (1), Sex (1), Expiry (6), CD (1), Nationality (3), Opt2 (11), Composite CD (1)
        dob_raw = l2[0:6]
        dob_cd_claimed = l2[6]
        sex = l2[7]
        expiry_raw = l2[8:14]
        expiry_cd_claimed = l2[14]
        nationality = l2[15:18].replace("<", "")
        opt2 = l2[18:29]
        fields["optional_data_2"] = opt2.replace("<", "")
        composite_cd_claimed = l2[29]

        # Line 3: Name
        name_parts = l3.split("<<", 1)
        surname = name_parts[0].replace("<", " ").strip()
        given_names = (
            name_parts[1].replace("<", " ").strip() if len(name_parts) > 1 else ""
        )

        # Validate check digits
        if not doc_num_cd_claimed.isdigit() or int(
            doc_num_cd_claimed
        ) != calculate_icao_check_digit(doc_number_raw):
            checksum_failures.append("document_number_checksum")

        if not dob_cd_claimed.isdigit() or int(
            dob_cd_claimed
        ) != calculate_icao_check_digit(dob_raw):
            checksum_failures.append("date_of_birth_checksum")

        if not expiry_cd_claimed.isdigit() or int(
            expiry_cd_claimed
        ) != calculate_icao_check_digit(expiry_raw):
            checksum_failures.append("expiry_date_checksum")

        # Composite check digit over l1[5:30] + l2[0:7] + l2[8:15] + l2[18:29]
        comp_data = l1[5:30] + l2[0:7] + l2[8:15] + l2[18:29]
        if not composite_cd_claimed.isdigit() or int(
            composite_cd_claimed
        ) != calculate_icao_check_digit(comp_data):
            checksum_failures.append("composite_checksum")

        _, is_expired = _parse_yy_mm_dd(expiry_raw)

        fields = {
            "document_type": doc_type or "I",
            "issuer": issuer_country,
            "document_number": doc_number,
            "surname": surname,
            "given_names": given_names,
            "nationality": nationality,
            "date_of_birth": dob_raw,
            "sex": sex if sex in ("M", "F", "X") else "X",
            "expiry_date": expiry_raw,
            "is_expired": is_expired,
        }

    # -------------------------------------------------------------------------
    # Format: TD2 (Official Travel Doc / Visa - 2 lines of 36 chars)
    # -------------------------------------------------------------------------
    elif num_lines == 2 and line_lens[0] == 36 and line_lens[1] == 36:
        doc_format = "TD2"
        l1, l2 = lines[0], lines[1]

        doc_type = l1[0:2].replace("<", "")
        issuer_country = l1[2:5].replace("<", "")
        name_parts = l1[5:36].split("<<", 1)
        surname = name_parts[0].replace("<", " ").strip()
        given_names = (
            name_parts[1].replace("<", " ").strip() if len(name_parts) > 1 else ""
        )

        doc_number_raw = l2[0:9]
        doc_number = doc_number_raw.replace("<", "")
        doc_num_cd_claimed = l2[9]
        nationality = l2[10:13].replace("<", "")
        dob_raw = l2[13:19]
        dob_cd_claimed = l2[19]
        sex = l2[20]
        expiry_raw = l2[21:27]
        expiry_cd_claimed = l2[27]
        composite_cd_claimed = l2[35]

        if not doc_num_cd_claimed.isdigit() or int(
            doc_num_cd_claimed
        ) != calculate_icao_check_digit(doc_number_raw):
            checksum_failures.append("document_number_checksum")

        if not dob_cd_claimed.isdigit() or int(
            dob_cd_claimed
        ) != calculate_icao_check_digit(dob_raw):
            checksum_failures.append("date_of_birth_checksum")

        if not expiry_cd_claimed.isdigit() or int(
            expiry_cd_claimed
        ) != calculate_icao_check_digit(expiry_raw):
            checksum_failures.append("expiry_date_checksum")

        comp_data = l2[0:10] + l2[13:20] + l2[21:35]
        if not composite_cd_claimed.isdigit() or int(
            composite_cd_claimed
        ) != calculate_icao_check_digit(comp_data):
            checksum_failures.append("composite_checksum")

        _, is_expired = _parse_yy_mm_dd(expiry_raw)

        fields = {
            "document_type": doc_type or "V",
            "issuer": issuer_country,
            "document_number": doc_number,
            "surname": surname,
            "given_names": given_names,
            "nationality": nationality,
            "date_of_birth": dob_raw,
            "sex": sex if sex in ("M", "F", "X") else "X",
            "expiry_date": expiry_raw,
            "is_expired": is_expired,
        }

    else:
        return {
            "format": "invalid_dimensions",
            "mrz_valid": False,
            "checksum_failures": ["mismatched_line_lengths"],
            "fields": {},
            "line_lengths": line_lens,
        }

    mrz_valid = len(checksum_failures) == 0

    return {
        "format": doc_format,
        "mrz_valid": mrz_valid,
        "checksum_failures": checksum_failures,
        "fields": fields,
    }


def analyze_document_geometry(
    image: Image.Image,
    claimed_doc_type: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Evaluates physical dimensions, aspect ratio, and orientation against
    standard ISO/IEC 7810 document geometry formats.
    """
    w, h = image.size
    aspect = round(float(w) / float(h), 3)

    # Standard landscape normalization
    ratio = aspect if aspect >= 1.0 else round(1.0 / (aspect + 1e-6), 3)

    is_td1 = abs(ratio - ASPECT_RATIO_TD1) <= ASPECT_RATIO_TOLERANCE
    is_td2 = abs(ratio - ASPECT_RATIO_TD2) <= ASPECT_RATIO_TOLERANCE
    is_td3 = abs(ratio - ASPECT_RATIO_TD3) <= ASPECT_RATIO_TOLERANCE

    likely_format = "unknown"
    if is_td1:
        likely_format = "ID-1 (National ID / License)"
    elif is_td3:
        likely_format = "ID-3 (Passport Data Page)"
    elif is_td2:
        likely_format = "ID-2 (Official Doc / Visa)"

    # Check alignment with claimed doc type
    geometry_consistent = True
    if claimed_doc_type:
        claimed_norm = claimed_doc_type.strip().lower()
        if "passport" in claimed_norm and not is_td3:
            geometry_consistent = False
        elif (
            ("id" in claimed_norm or "license" in claimed_norm)
            and not is_td1
            and not is_td2
        ):
            geometry_consistent = False

    return {
        "width": w,
        "height": h,
        "aspect_ratio": aspect,
        "normalized_ratio": ratio,
        "likely_format": likely_format,
        "geometry_consistent": geometry_consistent,
    }
