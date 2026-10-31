# Copyright (c) 2026 ARPA Hellenic Logical Systems
# SPDX-License-Identifier: MIT

"""Deterministic mock database for offline regional egress simulation."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

# Curated regional profiles with verified ASNs, ISPs, cities, and pricing conventions
REGIONAL_PROFILES: Dict[str, Dict[str, Any]] = {
    "US": {
        "country": "US",
        "country_name": "United States",
        "continent": "NA",
        "currency": "USD",
        "currency_symbol": "$",
        "sample_price": "$29.00",
        "cities": ["New York", "Los Angeles", "Chicago", "Miami", "Seattle"],
        "default_locale": "en-US",
        "gdpr_governed": False,
        "nodes": {
            "residential": [
                {
                    "ip": "198.51.100.12",
                    "city": "New York",
                    "asn": 7922,
                    "isp": "Comcast Cable Communications, LLC",
                    "network_type": "residential",
                    "latency_ms": 18.2,
                },
                {
                    "ip": "198.51.100.45",
                    "city": "Los Angeles",
                    "asn": 7018,
                    "isp": "AT&T Services, Inc.",
                    "network_type": "residential",
                    "latency_ms": 22.4,
                },
            ],
            "datacenter": [
                {
                    "ip": "54.210.14.88",
                    "city": "Ashburn",
                    "asn": 16509,
                    "isp": "Amazon.com, Inc.",
                    "network_type": "datacenter",
                    "latency_ms": 9.1,
                }
            ],
            "mobile": [
                {
                    "ip": "172.56.21.99",
                    "city": "Chicago",
                    "asn": 21928,
                    "isp": "T-Mobile USA, Inc.",
                    "network_type": "mobile",
                    "latency_ms": 45.6,
                }
            ],
        },
    },
    "GB": {
        "country": "GB",
        "country_name": "United Kingdom",
        "continent": "EU",
        "currency": "GBP",
        "currency_symbol": "£",
        "sample_price": "£22.00",
        "cities": ["London", "Manchester", "Edinburgh", "Birmingham"],
        "default_locale": "en-GB",
        "gdpr_governed": True,
        "cookie_consent_provider": "OneTrust",
        "path_prefix": "/uk",
        "nodes": {
            "residential": [
                {
                    "ip": "82.165.197.42",
                    "city": "London",
                    "asn": 2856,
                    "isp": "British Telecommunications PLC",
                    "network_type": "residential",
                    "latency_ms": 24.1,
                },
                {
                    "ip": "82.165.197.89",
                    "city": "Manchester",
                    "asn": 5089,
                    "isp": "Virgin Media Limited",
                    "network_type": "residential",
                    "latency_ms": 26.5,
                },
            ],
            "datacenter": [
                {
                    "ip": "185.86.151.10",
                    "city": "London",
                    "asn": 13030,
                    "isp": "Init7 (UK) Ltd",
                    "network_type": "datacenter",
                    "latency_ms": 11.3,
                }
            ],
            "mobile": [
                {
                    "ip": "212.58.244.70",
                    "city": "London",
                    "asn": 12576,
                    "isp": "EE Limited",
                    "network_type": "mobile",
                    "latency_ms": 52.8,
                }
            ],
        },
    },
    "DE": {
        "country": "DE",
        "country_name": "Germany",
        "continent": "EU",
        "currency": "EUR",
        "currency_symbol": "€",
        "sample_price": "€25.00",
        "cities": ["Frankfurt", "Berlin", "Munich", "Hamburg"],
        "default_locale": "de-DE",
        "gdpr_governed": True,
        "cookie_consent_provider": "Usercentrics",
        "path_prefix": "/de",
        "nodes": {
            "residential": [
                {
                    "ip": "185.190.24.8",
                    "city": "Frankfurt",
                    "asn": 3320,
                    "isp": "Deutsche Telekom AG",
                    "network_type": "residential",
                    "latency_ms": 19.5,
                },
                {
                    "ip": "185.190.24.60",
                    "city": "Berlin",
                    "asn": 3209,
                    "isp": "Vodafone GmbH",
                    "network_type": "residential",
                    "latency_ms": 21.0,
                },
            ],
            "datacenter": [
                {
                    "ip": "88.198.42.12",
                    "city": "Falkenstein",
                    "asn": 24940,
                    "isp": "Hetzner Online GmbH",
                    "network_type": "datacenter",
                    "latency_ms": 13.8,
                }
            ],
            "mobile": [
                {
                    "ip": "178.25.10.33",
                    "city": "Munich",
                    "asn": 3209,
                    "isp": "Vodafone Deutschland Mobile",
                    "network_type": "mobile",
                    "latency_ms": 48.0,
                }
            ],
        },
    },
    "JP": {
        "country": "JP",
        "country_name": "Japan",
        "continent": "AS",
        "currency": "JPY",
        "currency_symbol": "¥",
        "sample_price": "¥3,800",
        "cities": ["Tokyo", "Osaka", "Nagoya", "Fukuoka"],
        "default_locale": "ja-JP",
        "gdpr_governed": False,
        "path_prefix": "/jp",
        "nodes": {
            "residential": [
                {
                    "ip": "133.242.18.90",
                    "city": "Tokyo",
                    "asn": 4713,
                    "isp": "NTT Communications Corporation",
                    "network_type": "residential",
                    "latency_ms": 32.1,
                },
                {
                    "ip": "133.242.18.114",
                    "city": "Osaka",
                    "asn": 2516,
                    "isp": "KDDI Corporation",
                    "network_type": "residential",
                    "latency_ms": 35.6,
                },
            ],
            "datacenter": [
                {
                    "ip": "160.16.200.4",
                    "city": "Tokyo",
                    "asn": 9370,
                    "isp": "SAKURA Internet Inc.",
                    "network_type": "datacenter",
                    "latency_ms": 14.2,
                }
            ],
            "mobile": [
                {
                    "ip": "126.150.12.8",
                    "city": "Tokyo",
                    "asn": 17676,
                    "isp": "SoftBank Corp.",
                    "network_type": "mobile",
                    "latency_ms": 58.7,
                }
            ],
        },
    },
    "FR": {
        "country": "FR",
        "country_name": "France",
        "continent": "EU",
        "currency": "EUR",
        "currency_symbol": "€",
        "sample_price": "€25.00",
        "cities": ["Paris", "Lyon", "Marseille"],
        "default_locale": "fr-FR",
        "gdpr_governed": True,
        "cookie_consent_provider": "Didomi",
        "path_prefix": "/fr",
        "nodes": {
            "residential": [
                {
                    "ip": "86.200.14.55",
                    "city": "Paris",
                    "asn": 3215,
                    "isp": "Orange S.A.",
                    "network_type": "residential",
                    "latency_ms": 20.4,
                }
            ],
            "datacenter": [
                {
                    "ip": "51.15.40.10",
                    "city": "Paris",
                    "asn": 12876,
                    "isp": "Scaleway S.A.S.",
                    "network_type": "datacenter",
                    "latency_ms": 10.9,
                }
            ],
            "mobile": [
                {
                    "ip": "92.103.11.22",
                    "city": "Paris",
                    "asn": 12322,
                    "isp": "Free Mobile SAS",
                    "network_type": "mobile",
                    "latency_ms": 50.1,
                }
            ],
        },
    },
    "CA": {
        "country": "CA",
        "country_name": "Canada",
        "continent": "NA",
        "currency": "CAD",
        "currency_symbol": "C$",
        "sample_price": "C$38.00",
        "cities": ["Toronto", "Montreal", "Vancouver"],
        "default_locale": "en-CA",
        "gdpr_governed": False,
        "path_prefix": "/ca",
        "nodes": {
            "residential": [
                {
                    "ip": "142.112.55.10",
                    "city": "Toronto",
                    "asn": 577,
                    "isp": "BACOM - Bell Canada",
                    "network_type": "residential",
                    "latency_ms": 23.8,
                }
            ],
            "datacenter": [
                {
                    "ip": "192.99.10.88",
                    "city": "Montreal",
                    "asn": 16276,
                    "isp": "OVH Hosting, Inc.",
                    "network_type": "datacenter",
                    "latency_ms": 15.0,
                }
            ],
            "mobile": [
                {
                    "ip": "208.76.12.3",
                    "city": "Toronto",
                    "asn": 852,
                    "isp": "TELUS Communications Inc.",
                    "network_type": "mobile",
                    "latency_ms": 47.9,
                }
            ],
        },
    },
    "AU": {
        "country": "AU",
        "country_name": "Australia",
        "continent": "OC",
        "currency": "AUD",
        "currency_symbol": "A$",
        "sample_price": "A$42.00",
        "cities": ["Sydney", "Melbourne", "Brisbane"],
        "default_locale": "en-AU",
        "gdpr_governed": False,
        "path_prefix": "/au",
        "nodes": {
            "residential": [
                {
                    "ip": "120.144.10.5",
                    "city": "Sydney",
                    "asn": 1221,
                    "isp": "Telstra Corporation Ltd",
                    "network_type": "residential",
                    "latency_ms": 38.6,
                }
            ],
            "datacenter": [
                {
                    "ip": "139.130.4.5",
                    "city": "Sydney",
                    "asn": 7578,
                    "isp": "Optus Internet Pty Ltd",
                    "network_type": "datacenter",
                    "latency_ms": 22.0,
                }
            ],
            "mobile": [
                {
                    "ip": "101.160.2.14",
                    "city": "Melbourne",
                    "asn": 1221,
                    "isp": "Telstra Mobile",
                    "network_type": "mobile",
                    "latency_ms": 62.4,
                }
            ],
        },
    },
    "BR": {
        "country": "BR",
        "country_name": "Brazil",
        "continent": "SA",
        "currency": "BRL",
        "currency_symbol": "R$",
        "sample_price": "R$149,00",
        "cities": ["Sao Paulo", "Rio de Janeiro"],
        "default_locale": "pt-BR",
        "gdpr_governed": False,
        "path_prefix": "/br",
        "nodes": {
            "residential": [
                {
                    "ip": "177.135.20.10",
                    "city": "Sao Paulo",
                    "asn": 28573,
                    "isp": "Claro NXT Telecomunicacoes S.A.",
                    "network_type": "residential",
                    "latency_ms": 42.1,
                }
            ],
            "datacenter": [
                {
                    "ip": "200.147.67.142",
                    "city": "Sao Paulo",
                    "asn": 28624,
                    "isp": "Universo Online S.A.",
                    "network_type": "datacenter",
                    "latency_ms": 25.3,
                }
            ],
            "mobile": [
                {
                    "ip": "179.180.12.9",
                    "city": "Rio de Janeiro",
                    "asn": 26599,
                    "isp": "Telefonica Brasil S.A.",
                    "network_type": "mobile",
                    "latency_ms": 71.0,
                }
            ],
        },
    },
    "IN": {
        "country": "IN",
        "country_name": "India",
        "continent": "AS",
        "currency": "INR",
        "currency_symbol": "₹",
        "sample_price": "₹2,499",
        "cities": ["Mumbai", "Bengaluru", "Delhi"],
        "default_locale": "en-IN",
        "gdpr_governed": False,
        "path_prefix": "/in",
        "nodes": {
            "residential": [
                {
                    "ip": "157.34.120.4",
                    "city": "Mumbai",
                    "asn": 55836,
                    "isp": "Reliance Jio Infocomm Limited",
                    "network_type": "residential",
                    "latency_ms": 34.0,
                }
            ],
            "datacenter": [
                {
                    "ip": "115.112.4.90",
                    "city": "Bengaluru",
                    "asn": 4755,
                    "isp": "TATA Communications Limited",
                    "network_type": "datacenter",
                    "latency_ms": 19.8,
                }
            ],
            "mobile": [
                {
                    "ip": "122.161.44.12",
                    "city": "Delhi",
                    "asn": 24560,
                    "isp": "Bharti Airtel Ltd.",
                    "network_type": "mobile",
                    "latency_ms": 59.2,
                }
            ],
        },
    },
    "SG": {
        "country": "SG",
        "country_name": "Singapore",
        "continent": "AS",
        "currency": "SGD",
        "currency_symbol": "S$",
        "sample_price": "S$39.00",
        "cities": ["Singapore"],
        "default_locale": "en-SG",
        "gdpr_governed": False,
        "path_prefix": "/sg",
        "nodes": {
            "residential": [
                {
                    "ip": "116.14.80.20",
                    "city": "Singapore",
                    "asn": 7473,
                    "isp": "Singapore Telecommunications Ltd",
                    "network_type": "residential",
                    "latency_ms": 16.5,
                }
            ],
            "datacenter": [
                {
                    "ip": "103.253.14.10",
                    "city": "Singapore",
                    "asn": 133480,
                    "isp": "Equinix Asia Pacific",
                    "network_type": "datacenter",
                    "latency_ms": 8.4,
                }
            ],
            "mobile": [
                {
                    "ip": "119.74.10.88",
                    "city": "Singapore",
                    "asn": 4657,
                    "isp": "StarHub Ltd",
                    "network_type": "mobile",
                    "latency_ms": 38.1,
                }
            ],
        },
    },
    "NL": {
        "country": "NL",
        "country_name": "Netherlands",
        "continent": "EU",
        "currency": "EUR",
        "currency_symbol": "€",
        "sample_price": "€25.00",
        "cities": ["Amsterdam", "Rotterdam", "Utrecht"],
        "default_locale": "nl-NL",
        "gdpr_governed": True,
        "cookie_consent_provider": "Cookiebot",
        "path_prefix": "/nl",
        "nodes": {
            "residential": [
                {
                    "ip": "84.104.12.90",
                    "city": "Amsterdam",
                    "asn": 1136,
                    "isp": "KPN B.V.",
                    "network_type": "residential",
                    "latency_ms": 17.8,
                }
            ],
            "datacenter": [
                {
                    "ip": "95.211.80.12",
                    "city": "Amsterdam",
                    "asn": 60781,
                    "isp": "LeaseWeb Netherlands B.V.",
                    "network_type": "datacenter",
                    "latency_ms": 9.2,
                }
            ],
            "mobile": [
                {
                    "ip": "194.39.12.44",
                    "city": "Rotterdam",
                    "asn": 25459,
                    "isp": "Vodafone Libertel B.V.",
                    "network_type": "mobile",
                    "latency_ms": 42.0,
                }
            ],
        },
    },
    "CH": {
        "country": "CH",
        "country_name": "Switzerland",
        "continent": "EU",
        "currency": "CHF",
        "currency_symbol": "CHF",
        "sample_price": "CHF 28.00",
        "cities": ["Zurich", "Geneva", "Bern"],
        "default_locale": "de-CH",
        "gdpr_governed": True,
        "cookie_consent_provider": "OneTrust",
        "path_prefix": "/ch",
        "nodes": {
            "residential": [
                {
                    "ip": "178.197.80.15",
                    "city": "Zurich",
                    "asn": 3303,
                    "isp": "Swisscom (Schweiz) AG",
                    "network_type": "residential",
                    "latency_ms": 18.0,
                }
            ],
            "datacenter": [
                {
                    "ip": "193.134.24.8",
                    "city": "Geneva",
                    "asn": 13030,
                    "isp": "Init7 (Switzerland) Ltd",
                    "network_type": "datacenter",
                    "latency_ms": 11.0,
                }
            ],
            "mobile": [
                {
                    "ip": "194.230.14.7",
                    "city": "Bern",
                    "asn": 6734,
                    "isp": "Sunrise UPC LLC",
                    "network_type": "mobile",
                    "latency_ms": 44.5,
                }
            ],
        },
    },
    "KR": {
        "country": "KR",
        "country_name": "South Korea",
        "continent": "AS",
        "currency": "KRW",
        "currency_symbol": "₩",
        "sample_price": "₩38,000",
        "cities": ["Seoul", "Busan", "Incheon"],
        "default_locale": "ko-KR",
        "gdpr_governed": False,
        "path_prefix": "/kr",
        "nodes": {
            "residential": [
                {
                    "ip": "121.134.12.90",
                    "city": "Seoul",
                    "asn": 4766,
                    "isp": "Korea Telecom",
                    "network_type": "residential",
                    "latency_ms": 15.2,
                }
            ],
            "datacenter": [
                {
                    "ip": "211.233.10.4",
                    "city": "Seoul",
                    "asn": 9286,
                    "isp": "SK Broadband Co Ltd",
                    "network_type": "datacenter",
                    "latency_ms": 10.1,
                }
            ],
            "mobile": [
                {
                    "ip": "223.38.10.19",
                    "city": "Busan",
                    "asn": 9644,
                    "isp": "SK Telecom",
                    "network_type": "mobile",
                    "latency_ms": 36.8,
                }
            ],
        },
    },
    "SE": {
        "country": "SE",
        "country_name": "Sweden",
        "continent": "EU",
        "currency": "SEK",
        "currency_symbol": "kr",
        "sample_price": "299 kr",
        "cities": ["Stockholm", "Gothenburg"],
        "default_locale": "sv-SE",
        "gdpr_governed": True,
        "cookie_consent_provider": "Cookiebot",
        "path_prefix": "/se",
        "nodes": {
            "residential": [
                {
                    "ip": "81.230.12.44",
                    "city": "Stockholm",
                    "asn": 3301,
                    "isp": "Telia Company AB",
                    "network_type": "residential",
                    "latency_ms": 22.0,
                }
            ],
            "datacenter": [
                {
                    "ip": "194.236.4.10",
                    "city": "Stockholm",
                    "asn": 1653,
                    "isp": "Sunet (Swedish University Network)",
                    "network_type": "datacenter",
                    "latency_ms": 12.0,
                }
            ],
            "mobile": [
                {
                    "ip": "213.115.10.8",
                    "city": "Gothenburg",
                    "asn": 3301,
                    "isp": "Telia Mobile Sweden",
                    "network_type": "mobile",
                    "latency_ms": 46.2,
                }
            ],
        },
    },
    "ZA": {
        "country": "ZA",
        "country_name": "South Africa",
        "continent": "AF",
        "currency": "ZAR",
        "currency_symbol": "R",
        "sample_price": "R499.00",
        "cities": ["Johannesburg", "Cape Town", "Durban"],
        "default_locale": "en-ZA",
        "gdpr_governed": False,
        "path_prefix": "/za",
        "nodes": {
            "residential": [
                {
                    "ip": "105.184.22.8",
                    "city": "Johannesburg",
                    "asn": 37105,
                    "isp": "Liquid Telecommunications",
                    "network_type": "residential",
                    "latency_ms": 48.0,
                }
            ],
            "datacenter": [
                {
                    "ip": "197.80.4.12",
                    "city": "Cape Town",
                    "asn": 37611,
                    "isp": "Afrihost Pty Ltd",
                    "network_type": "datacenter",
                    "latency_ms": 28.5,
                }
            ],
            "mobile": [
                {
                    "ip": "196.11.235.1",
                    "city": "Durban",
                    "asn": 36907,
                    "isp": "MTN SA",
                    "network_type": "mobile",
                    "latency_ms": 78.4,
                }
            ],
        },
    },
    "AE": {
        "country": "AE",
        "country_name": "United Arab Emirates",
        "continent": "AS",
        "currency": "AED",
        "currency_symbol": "AED",
        "sample_price": "AED 109.00",
        "cities": ["Dubai", "Abu Dhabi"],
        "default_locale": "ar-AE",
        "gdpr_governed": False,
        "path_prefix": "/ae",
        "nodes": {
            "residential": [
                {
                    "ip": "94.200.12.8",
                    "city": "Dubai",
                    "asn": 5384,
                    "isp": "Emirates Telecommunications Corporation (Etisalat)",
                    "network_type": "residential",
                    "latency_ms": 29.5,
                }
            ],
            "datacenter": [
                {
                    "ip": "185.14.28.10",
                    "city": "Dubai",
                    "asn": 58244,
                    "isp": "du - Emirates Integrated Telecommunications Company",
                    "network_type": "datacenter",
                    "latency_ms": 16.0,
                }
            ],
            "mobile": [
                {
                    "ip": "94.205.10.12",
                    "city": "Abu Dhabi",
                    "asn": 5384,
                    "isp": "Etisalat Mobile",
                    "network_type": "mobile",
                    "latency_ms": 55.0,
                }
            ],
        },
    },
}


def get_country_profile(country_code: str) -> Optional[Dict[str, Any]]:
    """Look up regional profile by ISO 2-letter country code."""
    if not country_code:
        return None
    return REGIONAL_PROFILES.get(country_code.upper().strip())


def get_node_for_region(
    country_code: str,
    network_type: str = "residential",
    city: Optional[str] = None,
    failover_index: int = 0,
) -> Dict[str, Any]:
    """Retrieve an exit node for a given region, network type, and optional city."""
    profile = get_country_profile(country_code)
    if not profile:
        profile = REGIONAL_PROFILES["US"]

    pool = profile["nodes"].get(network_type) or profile["nodes"]["residential"]

    # Filter by city if specified
    if city:
        city_lower = city.lower().strip()
        matching_city = [n for n in pool if n.get("city", "").lower() == city_lower]
        if matching_city:
            pool = matching_city

    idx = failover_index % len(pool)
    selected = dict(pool[idx])
    selected["country"] = profile["country"]
    selected["country_name"] = profile["country_name"]
    return selected


def list_all_supported_regions(
    continent: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """List all supported countries and their pool capabilities."""
    results: List[Dict[str, Any]] = []
    cont_upper = continent.upper().strip() if continent else None

    for code, prof in sorted(REGIONAL_PROFILES.items()):
        if cont_upper and prof.get("continent") != cont_upper:
            continue
        results.append(
            {
                "country": prof["country"],
                "country_name": prof["country_name"],
                "continent": prof["continent"],
                "currency": prof["currency"],
                "currency_symbol": prof["currency_symbol"],
                "cities": list(prof["cities"]),
                "network_types": sorted(list(prof["nodes"].keys())),
                "sample_price": prof["sample_price"],
                "gdpr_governed": prof["gdpr_governed"],
            }
        )
    return results
