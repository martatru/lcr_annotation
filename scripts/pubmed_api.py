import httpx
import asyncio
import logging
from typing import List
from lxml import etree as ET
import json
import os
import re

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class PMCRegexMiner:

    def __init__(self, regex_patterns: List[str]):
        self.base = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/"
        self.timeout = httpx.Timeout(60.0)
        self.api_key = os.getenv("NCBI_API_KEY")

        # regex filter
        self.patterns = [re.compile(p, re.IGNORECASE) for p in regex_patterns]

        # SAFE SEARCH TERMS (PMC query ≠ regex!)
        self.search_terms = [
            "low complexity",
            "tandem repeat",
            "microsatellite",
            "simple sequence repeat",
            "intrinsically disordered",
            "compositionally biased",
            "repeat rich"
        ]

    # -----------------------------
    # BUILD QUERY
    # -----------------------------
    def _build_query(self) -> str:
        return " OR ".join(self.search_terms)

    # -----------------------------
    # SEARCH PMC
    # -----------------------------
    async def _search_pmc(self, client: httpx.AsyncClient, max_total: int):

        url = self.base + "esearch.fcgi"

        params = {
            "db": "pmc",
            "term": self._build_query(),
            "retmode": "json",
            "retmax": max_total,
            "sort": "relevance"
        }

        if self.api_key:
            params["api_key"] = self.api_key

        await asyncio.sleep(0.34)

        try:
            r = await client.get(url, params=params)
            r.raise_for_status()
            data = r.json()
        except Exception as e:
            logger.error(f"PMC search failed: {e}")
            return []

        ids = data.get("esearchresult", {}).get("idlist", [])

        return list(dict.fromkeys(ids))[:max_total]

    # -----------------------------
    # FETCH ARTICLE
    # -----------------------------
    async def _fetch_pmc(self, client: httpx.AsyncClient, pmc_id: str):

        url = self.base + "efetch.fcgi"

        params = {
            "db": "pmc",
            "id": pmc_id,
            "retmode": "xml"
        }

        if self.api_key:
            params["api_key"] = self.api_key

        await asyncio.sleep(0.34)

        try:
            r = await client.get(url, params=params)
            r.raise_for_status()
            return r.content
        except:
            return None

    # -----------------------------
    # AUTHORS
    # -----------------------------
    def _extract_authors(self, root):

        authors = []

        for contrib in root.findall(".//contrib"):
            if contrib.attrib.get("contrib-type") != "author":
                continue

            surname = contrib.findtext(".//surname")
            given = contrib.findtext(".//given-names")

            if surname and given:
                authors.append(f"{given} {surname}")
            elif surname:
                authors.append(surname)

        return authors

    # -----------------------------
    # SAFE SECTION EXTRACTION
    # -----------------------------
    def _extract_sections(self, root):

        sections = {
            "introduction": "",
            "results": "",
            "discussion": "",
            "conclusion": "",
        }

        for sec in root.findall(".//sec"):

            title = " ".join(sec.xpath("./title//text()")).lower()
            body = " ".join(sec.xpath(".//text()")).strip()

            if "intro" in title or "background" in title:
                sections["introduction"] += " " + body

            elif "result" in title:
                sections["results"] += " " + body

            elif "discussion" in title:
                sections["discussion"] += " " + body

            elif "conclusion" in title:
                sections["conclusion"] += " " + body

        return sections

    # -----------------------------
    # PARSE XML
    # -----------------------------
    def _parse(self, xml: bytes):

        root = ET.fromstring(xml)

        def get(xpath):
            return " ".join(root.xpath(xpath)).strip()

        sections = self._extract_sections(root)

        return {
            "title": get(".//article-title//text()"),
            "abstract": " ".join(root.xpath(".//abstract//text()")).strip(),
            "authors": self._extract_authors(root),
            **sections
        }

    # -----------------------------
    # REGEX FILTER
    # -----------------------------
    def _match(self, text: str) -> bool:
        return any(p.search(text) for p in self.patterns)

    # -----------------------------
    # PIPELINE
    # -----------------------------
    async def run(self, max_results: int = 5000):

        async with httpx.AsyncClient(timeout=self.timeout) as client:

            pmc_ids = await self._search_pmc(client, max_total=max_results * 2)

            logger.info(f"Fetched IDs: {len(pmc_ids)}")

            results = []
            seen = set()

            for i, pmc_id in enumerate(pmc_ids):

                if pmc_id in seen:
                    continue
                seen.add(pmc_id)

                xml = await self._fetch_pmc(client, pmc_id)
                if not xml:
                    continue

                try:
                    data = self._parse(xml)
                except Exception:
                    continue

                full_text = " ".join([
                    data["title"],
                    data["abstract"],
                    data["introduction"],
                    data["results"],
                    data["discussion"],
                    data["conclusion"]
                ])

                if self._match(full_text):

                    results.append({
                        "pmc_id": pmc_id,
                        "title": data["title"],
                        "abstract": data["abstract"],
                        "introduction": data["introduction"],
                        "results": data["results"],
                        "discussion": data["discussion"],
                        "conclusion": data["conclusion"],
                        "authors": data["authors"]
                    })

                if len(results) >= max_results:
                    break

                if i % 50 == 0:
                    logger.info(f"Matched: {len(results)}")

        return results


# -----------------------------
# RUN
# -----------------------------
async def main():

    KEYWORDS = [
        r"low[- ]complexity",
        r"low complexity region",
        r"compositionally biased",
        r"\blcd\b",

        r"tandem repeat",
        r"microsatellite",
        r"simple sequence repeat",
        r"short tandem repeat",

        r"repeat[- ]rich",
        r"repetitive sequence",

        r"glycine[- ]rich",
        r"serine[- ]rich",
        r"glutamine[- ]rich",
        r"asparagine[- ]rich",
        r"alanine[- ]rich",
        r"proline[- ]rich",

        r"intrinsically disordered",
        r"\bidr\b",
        r"\bidp\b",
        r"protein disorder",
        r"disordered protein",
        r"disordered region"
    ]

    miner = PMCRegexMiner(KEYWORDS)

    results = await miner.run(max_results=5000)

    with open("pmc_lcr_full.json", "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)

    print(f"Saved {len(results)} papers -> pmc_lcr_full.json")


if __name__ == "__main__":
    asyncio.run(main())