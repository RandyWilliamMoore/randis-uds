# Randis UDS™ by Randy Moore. Original: https://github.com/RandyWilliamMoore/randis-uds · Support: https://ko-fi.com/moorescombinatoricsmatrix
import json
import re
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET

UA = "Randis UDS research hub (github.com/RandyWilliamMoore/randis-uds)"
SOURCES = {
    "openalex": "OpenAlex (250M+ scholarly works, citation counts)",
    "europepmc": "Europe PMC (life sciences + PubMed, abstracts)",
    "pubmed": "PubMed (NIH, medicine and psychology)",
    "arxiv": "arXiv (preprints: CS, maths, physics, q-bio)",
    "semantic": "Semantic Scholar (AI-indexed papers, citations)",
    "wikipedia": "Wikipedia (overviews and background)",
    "crossref": "Crossref (publisher records, DOIs)",
}
MAX_N = 25


def _get(url, accept="application/json", limit=3_000_000):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": accept})
    with urllib.request.urlopen(req, timeout=25) as r:
        return r.read(limit).decode("utf-8", "replace")


def _clean(s, n=1600):
    s = re.sub(r"<[^>]+>", " ", str(s or ""))
    return re.sub(r"\s+", " ", s).strip()[:n]


def _openalex(q, n, year):
    f = f"&filter=from_publication_date:{year}-01-01" if year else ""
    d = json.loads(_get(f"https://api.openalex.org/works?search={urllib.parse.quote(q)}&per-page={n}{f}"))
    out = []
    for w in d.get("results", []):
        inv = w.get("abstract_inverted_index") or {}
        words = sorted(((p, k) for k, ps in inv.items() for p in ps))
        src = ((w.get("primary_location") or {}).get("source") or {})
        out.append({"title": _clean(w.get("title"), 300), "year": w.get("publication_year"),
                    "authors": ", ".join(a["author"]["display_name"] for a in (w.get("authorships") or [])[:4] if a.get("author")),
                    "venue": src.get("display_name") or "", "url": w.get("doi") or w.get("id") or "",
                    "abstract": _clean(" ".join(k for _, k in words)), "cites": w.get("cited_by_count")})
    return out


def _europepmc(q, n, year):
    qq = q + (f" AND PUB_YEAR:[{year} TO 3000]" if year else "")
    d = json.loads(_get("https://www.ebi.ac.uk/europepmc/webservices/rest/search?format=json&resultType=core&pageSize="
                        f"{n}&query={urllib.parse.quote(qq)}"))
    out = []
    for r in (d.get("resultList") or {}).get("result", []):
        url = f"https://doi.org/{r['doi']}" if r.get("doi") else f"https://europepmc.org/article/{r.get('source', 'MED')}/{r.get('id', '')}"
        out.append({"title": _clean(r.get("title"), 300), "year": r.get("pubYear"), "authors": _clean(r.get("authorString"), 160),
                    "venue": _clean((r.get("journalInfo") or {}).get("journal", {}).get("title") or r.get("bookOrReportDetails", {}).get("publisher") if isinstance(r.get("journalInfo"), dict) else "", 120),
                    "url": url, "abstract": _clean(r.get("abstractText")), "cites": r.get("citedByCount")})
    return out


def _pubmed(q, n, year):
    term = q + (f" AND {year}:3000[dp]" if year else "")
    ids = json.loads(_get("https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi?db=pubmed&sort=relevance&retmode=json&retmax="
                          f"{n}&term={urllib.parse.quote(term)}"))["esearchresult"].get("idlist", [])
    if not ids:
        return []
    xml = _get("https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi?db=pubmed&retmode=xml&id=" + ",".join(ids), "text/xml")
    out = []
    for a in ET.fromstring(xml).iter("PubmedArticle"):
        pmid = a.findtext(".//PMID") or ""
        art = a.find(".//Article")
        if art is None:
            continue
        au = [f"{x.findtext('LastName') or ''} {x.findtext('Initials') or ''}".strip() for x in art.findall(".//Author")[:4]]
        out.append({"title": _clean("".join(art.find("ArticleTitle").itertext()) if art.find("ArticleTitle") is not None else "", 300),
                    "year": a.findtext(".//PubDate/Year") or (a.findtext(".//PubDate/MedlineDate") or "")[:4],
                    "authors": ", ".join(au), "venue": art.findtext(".//Journal/Title") or "",
                    "url": f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/",
                    "abstract": _clean(" ".join("".join(t.itertext()) for t in art.findall(".//AbstractText"))), "cites": None})
    return out


def _arxiv(q, n, year):
    words = "+AND+".join("all:" + urllib.parse.quote(w) for w in re.findall(r"[\w-]+", q)[:8])
    xml = _get(f"https://export.arxiv.org/api/query?search_query={words}&max_results={n}&sortBy=relevance", "application/atom+xml")
    ns = {"a": "http://www.w3.org/2005/Atom"}
    out = []
    for e in ET.fromstring(xml).findall("a:entry", ns):
        y = (e.findtext("a:published", "", ns) or "")[:4]
        if year and y and int(y) < int(year):
            continue
        out.append({"title": _clean(e.findtext("a:title", "", ns), 300), "year": y,
                    "authors": ", ".join(x.findtext("a:name", "", ns) for x in e.findall("a:author", ns)[:4]),
                    "venue": "arXiv preprint (not peer reviewed)", "url": e.findtext("a:id", "", ns),
                    "abstract": _clean(e.findtext("a:summary", "", ns)), "cites": None})
    return out


def _semantic(q, n, year):
    y = f"&year={year}-" if year else ""
    d = json.loads(_get(f"https://api.semanticscholar.org/graph/v1/paper/search?query={urllib.parse.quote(q)}&limit={n}{y}"
                        "&fields=title,year,authors,venue,url,abstract,citationCount,tldr"))
    return [{"title": _clean(p.get("title"), 300), "year": p.get("year"),
             "authors": ", ".join(a.get("name", "") for a in (p.get("authors") or [])[:4]), "venue": p.get("venue") or "",
             "url": p.get("url") or "", "abstract": _clean(p.get("abstract") or ((p.get("tldr") or {}).get("text"))),
             "cites": p.get("citationCount")} for p in d.get("data") or []]


def _wikipedia(q, n, year):
    d = json.loads(_get(f"https://en.wikipedia.org/w/rest.php/v1/search/page?q={urllib.parse.quote(q)}&limit={min(n, 10)}"))
    out = []
    for p in d.get("pages", []):
        out.append({"title": p.get("title"), "year": "", "authors": "Wikipedia", "venue": "Wikipedia",
                    "url": "https://en.wikipedia.org/wiki/" + urllib.parse.quote(str(p.get("key") or "")),
                    "abstract": _clean(p.get("excerpt")) + (" — " + _clean(p.get("description")) if p.get("description") else ""), "cites": None})
    return out


def _crossref(q, n, year):
    f = f"&filter=from-pub-date:{year}" if year else ""
    d = json.loads(_get(f"https://api.crossref.org/works?query={urllib.parse.quote(q)}&rows={n}{f}"
                        "&select=title,author,issued,container-title,DOI,abstract,is-referenced-by-count"))
    out = []
    for w in (d.get("message") or {}).get("items", []):
        out.append({"title": _clean((w.get("title") or [""])[0], 300),
                    "year": ((w.get("issued") or {}).get("date-parts") or [[None]])[0][0],
                    "authors": ", ".join(f"{a.get('given', '')} {a.get('family', '')}".strip() for a in (w.get("author") or [])[:4]),
                    "venue": (w.get("container-title") or [""])[0], "url": "https://doi.org/" + w.get("DOI", ""),
                    "abstract": _clean(w.get("abstract")), "cites": w.get("is-referenced-by-count")})
    return out


FN = {"openalex": _openalex, "europepmc": _europepmc, "pubmed": _pubmed, "arxiv": _arxiv,
      "semantic": _semantic, "wikipedia": _wikipedia, "crossref": _crossref}


def search(source, query, n=8, since=None):
    source, query = str(source or ""), str(query or "").strip()[:300]
    if source not in FN:
        return {"error": "Unknown source. Use one of: " + ", ".join(FN)}
    if not query:
        return {"error": "Nothing to search for."}
    try:
        n = max(1, min(int(n or 8), MAX_N))
        year = int(since) if since and str(since).isdigit() and 1900 < int(since) < 2100 else None
        rs = FN[source](query, n, year)
        for r in rs:
            r["source"] = source
        return {"source": source, "results": rs}
    except urllib.error.HTTPError as e:
        return {"error": f"{source} answered {e.code}" + (" (busy: try again in a minute)" if e.code == 429 else "")}
    except Exception as e:
        return {"error": f"{source}: {e}"}
