# Basis for Deepsearch

This reference preserves the rationale and observations recorded by upstream
[imozuru](https://github.com/MaryCache/imozuru/tree/ecb82c71b611872a0f49e783eda3bec987c80d91).
The upstream author collected the originals during a 2026-10-09 trial on search
methods. These are upstream source claims and trial observations, not new
verification performed for this adaptation.

Line numbers refer to files extracted with `fetch.py`, `pdftotext -layout`, or ax.
Different extraction tools can move the lines; locate a short exact quote when
checking a rule. Revisit the original passage before changing the rule it supports.

## Original source URLs

| File stem | URL |
|---|---|
| `bates-1989-berrypicking` | https://www.pages.gseis.ucla.edu/faculty/bates/articles/berrypicking.pdf |
| `ellis-1987-phd-behavioural-model` | https://etheses.whiterose.ac.uk/id/eprint/2975/1/DX093006.pdf |
| `kuhlthau-1991-inside-search-process` | https://tefkos.rutgers-sci.domains/Courses/612/Articles/Kuhlthau_Inside_91.pdf |
| `arxiv-2609.01294-explore-before-committing` | https://arxiv.org/pdf/2609.01294 |
| `arxiv-2608.02009-halt` | https://arxiv.org/pdf/2608.02009 |
| `arxiv-2602.03304-to-search-or-not` | https://arxiv.org/pdf/2602.03304 |
| `kastner-2007-horizon-estimate` | https://pmc.ncbi.nlm.nih.gov/articles/PMC2655834/ |
| `eumesy-unknown-terms` | https://speakerdeck.com/eumesy/examine-the-meaning-of-unknown-terms |
| `arxiv-2505.09316-scent-of-knowledge` | https://arxiv.org/pdf/2505.09316 |

## Rules and sources

| Rule | Source | Original location |
|---|---|---|
| Let the question evolve while collecting useful fragments. | Bates 1989, “The design of browsing and berrypicking techniques for the online search interface” | `bates-1989-berrypicking.txt` |
| Follow six moves: references, citations, journal scanning, nearby browsing, subject indexes, and authors. | Bates 1989 | Same file, lines 295–355 |
| Citation chaining avoids having to express the subject in the right words. | Bates 1989 | Same file, lines 297–302 |
| Starting, chaining, browsing, differentiating, monitoring, and extracting. | Ellis 1987 PhD thesis; basis for the paywalled 1989 JoD article | `ellis-1987-phd-behavioural-model.txt`, line 64; contents at 165–276 |
| Early confusion is normal; detailed notes can cause premature closure. Gather potentially relevant facts. | Kuhlthau 1991, “Inside the Search Process” | `kuhlthau-1991-inside-search-process.txt`, lines 345–368 |
| Committing to one direction reinforces it in later searches; compare hypothesis branches first. | Zhou et al. 2026, “Explore Before Committing” (HypoSearch), arXiv 2609.01294 | `arxiv-2609.01294-explore-before-committing.txt`, abstract |
| Stop based on evidence supporting the required claims, not confidence. | Roh & Han 2026, “HALT”, arXiv 2608.02009 | `arxiv-2608.02009-halt.txt`, abstract |
| Distinguish over-search after sufficient evidence from under-search that stops too early. | Zhang et al. 2026, “To Search or Not to Search”, arXiv 2602.03304 | `arxiv-2602.03304-to-search-or-not.txt`, abstract |
| Estimate unseen material from overlap between independent searches (capture-mark-recapture). | Kastner et al. 2007, “Estimating the Horizon of Articles to Decide When to Stop Searching” | `kastner-2007-horizon-estimate.md`, line 51 |
| Resolve unfamiliar terms from broad to narrow: encyclopedias, specialist dictionaries, textbooks/lectures, surveys, originals. | Sho Yokoi 2017, “Examine the meaning of unknown terms” | `eumesy-unknown-terms.md`, lines 343–373 |
| Choose the next lead by information scent. | Pirolli & Card 1999, “Information foraging”, DOI 10.1037/0033-295x.106.4.643 | Original not obtained (paywalled); an LLM application is in `arxiv-2505.09316-scent-of-knowledge.txt` |

## Upstream workflow observations

- Five of eleven search-result URLs led to 404s, login walls, or HTML posing as a
  PDF. Inspect fetched content rather than trusting URLs or response status.
- Three papers on LLM search agents cited none of Bates, Kuhlthau, Ellis, or
  Marchionini, and only one information-foraging source. This is an observation
  about that sample, not a claim about all AI research.
- OpenAlex full-text queries ranked commentary above originals; title-only queries
  sorted by citation count worked better. Indexed titles may omit subtitles, so
  prefer DOI lookup.
- Workers' “Not searched” sections became useful lead lists for the next round.

## Canonical works not yet read upstream

- Pirolli & Card 1999 and Marchionini 2006, “Exploratory search” (paywalled).
- Case & Given 2016, “Looking for Information”, an information-behavior textbook.
- Wilson 1999, “Models in information behaviour research”; Booth 2010, “How much
  searching is enough?”; TARCiS 2024 guidance on citation searching.

## Lessons from three trial topics (2026-10-09)

The upstream trials covered research on search methods, making AI-generated images
editable (two runs in a paper-rich field), and a digital-painting style whose
knowledge was mainly in practitioners' posts.

- Existence-only claims filled in one round while missing the request's core
  condition. Retain an exact substantive user condition and make at least half the
  claims require reading an original.
- `chain.py` helped with older papers but not papers roughly a year old, whose
  citations were not yet indexed.
- Practitioner topics required `fetch.py` and web search rather than DOIs or
  `chain.py`. Deeper search recovered source categories missed by standard search;
  key material sometimes remained behind X, pixiv, and Xiaohongshu login walls.
- A genuine Japanese article had only 2,904 characters; a 3,000-character floor
  intended for English papers rejected it.
- The same applies to PDFs. A PDF whose non-whitespace text is more than 30% CJK
  uses the HTML floor of 1,000 characters.
- Search reports relied on snippets. One Type-R description disagreed with its
  original source, motivating explicit unverified labels until the source is read.
