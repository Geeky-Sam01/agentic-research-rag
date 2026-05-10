import difflib
import logging
import re
from collections import defaultdict
from typing import Dict, List, Optional, Set

from pydantic import BaseModel

from app.services.agent_tools import _get_all_schemes

logger = logging.getLogger(__name__)

class FundMatch(BaseModel):
    scheme_code: str
    scheme_name: str
    score: float

class FundResolutionResult(BaseModel):
    resolved: bool
    confidence: float
    best_match: Optional[FundMatch] = None
    alternatives: List[FundMatch] = []
    query: str
    original_query: str
    resolution_reason: Optional[str] = None  # alias_match, exact_match, prefix_match, token_match, fuzzy_match

SCHEME_CACHE = {}
NORMALIZED_NAME_MAP = {}
TOKEN_INDEX = defaultdict(set)
ALIAS_INDEX: Dict[str, dict] = {}
_INDEX_BUILT = False

KNOWN_ALIASES = {
  "sbi bluechip": {
    "canonical_name": "SBI Large Cap Fund",
    "alias_type": "historical_name"
  },
  "sbi magnum tax gain": {
    "canonical_name": "SBI Long Term Equity Fund",
    "alias_type": "historical_name"
  },
  "sbi magnum midcap": {
    "canonical_name": "SBI Magnum Midcap Fund",
    "alias_type": "historical_name"
  },
  "sbi small cap": {
    "canonical_name": "SBI Small Cap Fund",
    "alias_type": "shorthand"
  },
  "sbi contra": {
    "canonical_name": "SBI Contra Fund",
    "alias_type": "shorthand"
  },
  "hdfc top 200": {
    "canonical_name": "HDFC Top 100 Fund",
    "alias_type": "historical_name"
  },
  "hdfc premier multicap": {
    "canonical_name": "HDFC Flexi Cap Fund",
    "alias_type": "historical_name"
  },
  "hdfc balanced": {
    "canonical_name": "HDFC Hybrid Equity Fund",
    "alias_type": "historical_name"
  },
  "hdfc prudence": {
    "canonical_name": "HDFC Balanced Advantage Fund",
    "alias_type": "historical_name"
  },
  "hdfc midcap opportunities": {
    "canonical_name": "HDFC Mid-Cap Opportunities Fund",
    "alias_type": "shorthand"
  },
  "icici pru bluechip": {
    "canonical_name": "ICICI Prudential Bluechip Fund",
    "alias_type": "abbreviation"
  },
  "icici focused bluechip": {
    "canonical_name": "ICICI Prudential Bluechip Fund",
    "alias_type": "shorthand"
  },
  "icici balanced": {
    "canonical_name": "ICICI Prudential Balanced Advantage Fund",
    "alias_type": "historical_name"
  },
  "icici value discovery": {
    "canonical_name": "ICICI Prudential Value Discovery Fund",
    "alias_type": "shorthand"
  },
  "axis long term equity": {
    "canonical_name": "Axis ELSS Tax Saver Fund",
    "alias_type": "historical_name"
  },
  "axis bluechip": {
    "canonical_name": "Axis Bluechip Fund",
    "alias_type": "shorthand"
  },
  "axis small cap": {
    "canonical_name": "Axis Small Cap Fund",
    "alias_type": "shorthand"
  },
  "mirae emerging bluechip": {
    "canonical_name": "Mirae Asset Large & Midcap Fund",
    "alias_type": "historical_name"
  },
  "mirae large and midcap": {
    "canonical_name": "Mirae Asset Large & Midcap Fund",
    "alias_type": "shorthand"
  },
  "mirae bluechip": {
    "canonical_name": "Mirae Asset Large & Midcap Fund",
    "alias_type": "colloquial"
  },
  "mirae tax saver": {
    "canonical_name": "Mirae Asset ELSS Tax Saver Fund",
    "alias_type": "shorthand"
  },
  "reliance growth": {
    "canonical_name": "Nippon India Growth Fund",
    "alias_type": "historical_name"
  },
  "reliance small cap": {
    "canonical_name": "Nippon India Small Cap Fund",
    "alias_type": "historical_name"
  },
  "reliance vision": {
    "canonical_name": "Nippon India Vision Fund",
    "alias_type": "historical_name"
  },
  "reliance tax saver": {
    "canonical_name": "Nippon India Tax Saver Fund",
    "alias_type": "historical_name"
  },
  "franklin prima": {
    "canonical_name": "Franklin India Prima Fund",
    "alias_type": "shorthand"
  },
  "franklin smaller companies": {
    "canonical_name": "Franklin India Smaller Companies Fund",
    "alias_type": "shorthand"
  },
  "franklin bluechip": {
    "canonical_name": "Franklin India Bluechip Fund",
    "alias_type": "shorthand"
  },
  "dsp blackrock top 100": {
    "canonical_name": "DSP Top 100 Equity Fund",
    "alias_type": "historical_name"
  },
  "dsp blackrock small cap": {
    "canonical_name": "DSP Small Cap Fund",
    "alias_type": "historical_name"
  },
  "dsp equity opportunities": {
    "canonical_name": "DSP Equity Opportunities Fund",
    "alias_type": "shorthand"
  },
  "kotak standard multicap": {
    "canonical_name": "Kotak Flexicap Fund",
    "alias_type": "historical_name"
  },
  "kotak select focus": {
    "canonical_name": "Kotak Focused Equity Fund",
    "alias_type": "historical_name"
  },
  "kotak opportunities": {
    "canonical_name": "Kotak Opportunities Fund",
    "alias_type": "shorthand"
  },
  "uti opportunities": {
    "canonical_name": "UTI Flexi Cap Fund",
    "alias_type": "historical_name"
  },
  "uti mastershare": {
    "canonical_name": "UTI Large Cap Fund",
    "alias_type": "historical_name"
  },
  "uti equity": {
    "canonical_name": "UTI Flexi Cap Fund",
    "alias_type": "shorthand"
  },
  "birla sun life frontline": {
    "canonical_name": "Aditya Birla Sun Life Frontline Equity Fund",
    "alias_type": "historical_name"
  },
  "birla tax relief 96": {
    "canonical_name": "Aditya Birla Sun Life ELSS Tax Relief 96",
    "alias_type": "historical_name"
  },
  "birla pure value": {
    "canonical_name": "Aditya Birla Sun Life Pure Value Fund",
    "alias_type": "shorthand"
  },
  "canara robeco emerging equities": {
    "canonical_name": "Canara Robeco Emerging Equities Fund",
    "alias_type": "shorthand"
  },
  "canara robeco bluechip": {
    "canonical_name": "Canara Robeco Bluechip Equity Fund",
    "alias_type": "shorthand"
  },
  "ppfas": {
    "canonical_name": "Parag Parikh Flexi Cap Fund",
    "alias_type": "abbreviation"
  },
  "parag parikh": {
    "canonical_name": "Parag Parikh Flexi Cap Fund",
    "alias_type": "colloquial"
  },
  "ppfas flexi cap": {
    "canonical_name": "Parag Parikh Flexi Cap Fund",
    "alias_type": "abbreviation"
  },
  "quant active": {
    "canonical_name": "Quant Active Fund",
    "alias_type": "shorthand"
  },
  "quant tax plan": {
    "canonical_name": "Quant ELSS Tax Saver Fund",
    "alias_type": "historical_name"
  },
  "quant small cap": {
    "canonical_name": "Quant Small Cap Fund",
    "alias_type": "shorthand"
  },
  "motilal nasdaq": {
    "canonical_name": "Motilal Oswal Nasdaq 100 FOF",
    "alias_type": "shorthand"
  },
  "motilal s&p 500": {
    "canonical_name": "Motilal Oswal S&P 500 Index Fund",
    "alias_type": "shorthand"
  },
  "motilal midcap": {
    "canonical_name": "Motilal Oswal Midcap Fund",
    "alias_type": "shorthand"
  },
  "edelweiss balanced advantage": {
    "canonical_name": "Edelweiss Balanced Advantage Fund",
    "alias_type": "shorthand"
  },
  "tata digital india": {
    "canonical_name": "Tata Digital India Fund",
    "alias_type": "shorthand"
  },
  "sundaram select midcap": {
    "canonical_name": "Sundaram Mid Cap Fund",
    "alias_type": "historical_name"
  },
  "l&t emerging businesses": {
    "canonical_name": "HSBC Small Cap Fund",
    "alias_type": "historical_name"
  },
  "l&t tax advantage": {
    "canonical_name": "HSBC ELSS Tax Saver Fund",
    "alias_type": "historical_name"
  }
}

def normalize_scheme_name(name: str) -> str:
    name = name.lower()
    name = name.replace("&", "and")
    name = re.sub(r'[^a-z0-9]', '', name)
    return name

def strip_query_noise(query: str) -> str:
    """Removes common conversational prefixes to isolate the fund name."""
    noise_patterns = [
        r"^show (?:me )?(?:the )?(?:details|nav|performance|holdings) (?:of|for) ",
        r"^what is (?:the )?(?:nav|performance|details|status) (?:of|for) ",
        r"^tell me (?:about|more about) ",
        r"^details (?:about|of|for) ",
        r"^calculate (?:sip|returns) (?:for|of) ",
        r"^performance (?:of|for) ",
        r"^compare ",
        r"^how is ",
        r"\b(?:mutual )?fund\b",
    ]
    query_clean = query.lower().strip()
    for pattern in noise_patterns:
        query_clean = re.sub(pattern, "", query_clean)
    
    # Remove trailing question marks
    query_clean = query_clean.rstrip("?").strip()
    return query_clean

def tokenize_name(name: str) -> Set[str]:
    name = name.lower().replace("&", "and")
    name = re.sub(r'[^a-z0-9\s]', ' ', name)
    tokens = set(name.split())
    stopwords = {"fund", "direct", "regular", "plan", "growth", "idcw", "option", "payout", "reinvestment"}
    return tokens - stopwords

def build_alias_index():
    """Maps manual aliases to canonical scheme IDs by resolving against the full scheme index."""
    global ALIAS_INDEX
    for alias_raw, data in KNOWN_ALIASES.items():
        norm_alias = normalize_scheme_name(alias_raw)
        canonical_name = data["canonical_name"]
        
        # Resolve canonical name to a code from NORMALIZED_NAME_MAP or Token Index
        # We try exact normalized match first
        norm_canonical = normalize_scheme_name(canonical_name)
        match = NORMALIZED_NAME_MAP.get(norm_canonical)
        
        if not match:
            # Fallback: find best token match for canonical name if not exact
            res = resolve_fund(canonical_name, skip_alias=True)
            if res.resolved and res.best_match:
                match = {"scheme_code": res.best_match.scheme_code, "scheme_name": res.best_match.scheme_name}
        
        if match:
            ALIAS_INDEX[norm_alias] = {
                "scheme_code": match["scheme_code"],
                "canonical_name": match["scheme_name"],
                "alias_type": data["alias_type"],
                "confidence_boost": 0.15
            }
            logger.debug(f"Alias Indexed: '{alias_raw}' -> '{match['scheme_name']}' ({match['scheme_code']})")
        else:
            logger.warning(f"Alias Failed: Could not resolve canonical fund '{canonical_name}' for alias '{alias_raw}'")

def build_index():
    global _INDEX_BUILT, SCHEME_CACHE, NORMALIZED_NAME_MAP, TOKEN_INDEX
    if _INDEX_BUILT:
        return
        
    all_schemes = _get_all_schemes()
    if not all_schemes:
        return
        
    SCHEME_CACHE = all_schemes
    
    for code, name in all_schemes.items():
        norm_name = normalize_scheme_name(name)
        NORMALIZED_NAME_MAP[norm_name] = {"scheme_code": code, "scheme_name": name}
        
        tokens = tokenize_name(name)
        for t in tokens:
            TOKEN_INDEX[t].add(code)
            
    _INDEX_BUILT = True
    
    # Build alias index after primary index is ready
    build_alias_index()
    
    logger.info(f"Fund Resolver Index built: {len(SCHEME_CACHE)} schemes, {len(ALIAS_INDEX)} aliases.")

def resolve_fund(query: str, skip_alias: bool = False) -> FundResolutionResult:
    build_index()
    
    # Pre-process: strip query noise to isolate potential fund name
    clean_query = strip_query_noise(query)
    norm_query = normalize_scheme_name(clean_query)
    
    if not norm_query:
        return FundResolutionResult(resolved=False, confidence=0.0, query=query, original_query=query)
        
    # STEP 1: Alias Lookup (Highest Priority)
    if not skip_alias and norm_query in ALIAS_INDEX:
        alias_data = ALIAS_INDEX[norm_query]
        fm = FundMatch(
            scheme_code=str(alias_data["scheme_code"]), 
            scheme_name=alias_data["canonical_name"], 
            score=0.98
        )
        logger.info(f"AliasResolver: query='{query}', resolved='{fm.scheme_name}', reason='alias_match', confidence=0.98")
        logger.info(f"ResolverMetrics: type='alias_match', query='{query}'")
        return FundResolutionResult(
            resolved=True, 
            confidence=0.98, 
            best_match=fm, 
            query=query, 
            original_query=query,
            resolution_reason="alias_match"
        )

    # STEP 2: Exact Normalized Match
    if norm_query in NORMALIZED_NAME_MAP:
        match_data = NORMALIZED_NAME_MAP[norm_query]
        fm = FundMatch(
            scheme_code=str(match_data["scheme_code"]), 
            scheme_name=match_data["scheme_name"], 
            score=1.0
        )
        logger.info(f"Resolver: query='{query}', resolved='{fm.scheme_name}', reason='exact_match', confidence=1.00")
        return FundResolutionResult(
            resolved=True, 
            confidence=1.0, 
            best_match=fm, 
            query=query, 
            original_query=query,
            resolution_reason="exact_match"
        )
        
    # STEP 3: Prefix Match
    prefix_matches = []
    for norm_name, data in NORMALIZED_NAME_MAP.items():
        if norm_name.startswith(norm_query):
            prefix_matches.append(data)
            
    if len(prefix_matches) == 1:
        fm = FundMatch(
            scheme_code=str(prefix_matches[0]["scheme_code"]),
            scheme_name=prefix_matches[0]["scheme_name"],
            score=0.95
        )
        logger.info(f"Resolver: query='{query}', resolved='{fm.scheme_name}', reason='prefix_match', confidence=0.95")
        return FundResolutionResult(
            resolved=True, 
            confidence=0.95, 
            best_match=fm, 
            query=query, 
            original_query=query,
            resolution_reason="prefix_match"
        )
    elif len(prefix_matches) > 1:
        sorted_prefixes = sorted(prefix_matches, key=lambda x: len(x["scheme_name"]))
        best = sorted_prefixes[0]
        fm = FundMatch(scheme_code=str(best["scheme_code"]), scheme_name=best["scheme_name"], score=0.90)
        alts = [FundMatch(scheme_code=str(x["scheme_code"]), scheme_name=x["scheme_name"], score=0.85) for x in sorted_prefixes[1:4]]
        logger.info(f"Resolver: query='{query}', resolved='{fm.scheme_name}', reason='prefix_match_multi', confidence=0.90")
        return FundResolutionResult(
            resolved=True, 
            confidence=0.90, 
            best_match=fm, 
            alternatives=alts, 
            query=query, 
            original_query=query,
            resolution_reason="prefix_match"
        )

    # STEP 4: Token-Based Candidate Filtering
    query_tokens = tokenize_name(query)
    if query_tokens:
        candidate_counts = defaultdict(int)
        for qt in query_tokens:
            matched_codes = set()
            for indexed_token, codes in TOKEN_INDEX.items():
                if indexed_token == qt or indexed_token.startswith(qt):
                    matched_codes.update(codes)
            for code in matched_codes:
                candidate_counts[code] += 1
                
        if candidate_counts:
            scored_candidates = []
            for code, count in candidate_counts.items():
                name = SCHEME_CACHE[code]
                scheme_tokens = tokenize_name(name)
                coverage = count / len(query_tokens)
                extra_tokens = len(scheme_tokens) - count
                penalty = extra_tokens * 0.05
                score = coverage - penalty
                
                if "direct" in name.lower() and "growth" in name.lower():
                    score += 0.15
                    
                scored_candidates.append((score, code, name))
                
            scored_candidates.sort(key=lambda x: x[0], reverse=True)
            
            best_score, best_code, best_name = scored_candidates[0]
            norm_score = max(0.0, min(0.98, best_score))
            
            if norm_score >= 0.7:
                fm = FundMatch(scheme_code=str(best_code), scheme_name=best_name, score=norm_score)
                alts = [FundMatch(scheme_code=str(c), scheme_name=n, score=max(0.0, min(0.98, s))) for s, c, n in scored_candidates[1:5]]
                resolved = norm_score >= 0.9
                logger.info(f"Resolver: query='{query}', resolved='{fm.scheme_name}', reason='token_match', confidence={norm_score:.2f}")
                return FundResolutionResult(
                    resolved=resolved,
                    confidence=norm_score,
                    best_match=fm,
                    alternatives=alts,
                    query=query,
                    original_query=query,
                    resolution_reason="token_match"
                )
                
    # STEP 5: Fuzzy Matching (fallback)
    fuzzy_candidates = []
    for code, name in SCHEME_CACHE.items():
        score = difflib.SequenceMatcher(None, norm_query, normalize_scheme_name(name)).ratio()
        if score > 0.6:
            if "direct" in name.lower() and "growth" in name.lower():
                score += 0.05
            fuzzy_candidates.append((score, code, name))
            
    if fuzzy_candidates:
        fuzzy_candidates.sort(key=lambda x: x[0], reverse=True)
        best_score, best_code, best_name = fuzzy_candidates[0]
        fm = FundMatch(scheme_code=str(best_code), scheme_name=best_name, score=best_score)
        alts = [FundMatch(scheme_code=str(c), scheme_name=n, score=s) for s, c, n in fuzzy_candidates[1:5]]
        resolved = best_score >= 0.9
        
        logger.info(f"Resolver: query='{query}', resolved='{fm.scheme_name}', reason='fuzzy_match', confidence={best_score:.2f}")
        return FundResolutionResult(
            resolved=resolved,
            confidence=best_score,
            best_match=fm,
            alternatives=alts,
            query=query,
            original_query=query,
            resolution_reason="fuzzy_match"
        )
        
    logger.info(f"Resolver: query='{query}', resolved='None', reason='unresolved', confidence=0.00")
    return FundResolutionResult(resolved=False, confidence=0.0, query=query, original_query=query, resolution_reason="unresolved")
