# Omni Suite — Shared Glossary (Ubiquitous Language)

This file defines the business vocabulary of the Omni Suite so that
humans and AI agents mean the same thing when they talk about the
pipeline. It follows the Domain-Driven Design practice of Ubiquitous
Language: when a term is used in an issue, a commit, or an agent
conversation, it should match a definition here. Terms are defined by
behavior, not by version or by internal code location; those details
live in PROJECT_STATUS, VERSION, and DECISIONS.md.

## pipeline

The three-stage localization process that turns a source document into
a translated document in a target format. Stage one, OPP, extracts the
document into standardized intermediate artifacts. Stage two, OL,
translates those artifacts between languages. Stage three, ORF,
backfills the translated content into a finished file. The pipeline can
be driven end to end by chaining the per-module CLIs or by chaining the
per-module MCP tools, passing the output of each step as the input of
the next.

See also: OPP, OL, ORF, MD channel, XLIFF channel.

## OPP

Omni Pre-Processor, the extraction stage of the pipeline and the first
module. It takes documents of many input formats, including DOCX, PPTX,
PDF, XLSX, CSV, JSON, XML, HTML, EPUB, EML, MSG, and images, detects the
format by magic bytes, and produces standardized intermediates:
Markdown, XLIFF, a skeleton archive, and the extraction manifests.
OPP is also the module that intentionally blocks PDF to XLIFF
conversion, because PDF structure is too lossy for clean XLIFF units.

See also: pipeline, extract, skeleton.zip, manifest.json, images.json.

## OL

Omni Localizer, the translation stage of the pipeline and the second
module. It translates Markdown and XLIFF artifacts between language
pairs using LLM-backed translation. Translation goes through a
protective shield, an LLM call, a repair pass, and an unshield, and can
be steered by glossary terms and translation memory lookups. After
translation, optional quality gates emit non-blocking warnings about
the output. OL never overwrites XLIFF sources; it fills the target
elements.

See also: pipeline, translate, shield/unshield, repair pass, quality
gates, glossary, translation memory (TM).

## ORF

Omni Re-Formatter, the backfill stage of the pipeline and the third
module. It takes translated Markdown or translated XLIFF and produces
the final output document. The Markdown channel renders into any of the
sixteen supported output formats. The XLIFF channel re-injects
translated text into the original document layout using the skeleton
archive produced by OPP, preserving fonts, styles, and image positions.
ORF also ships an agent orchestration layer in which a Foreman
decomposes jobs and routes them to format-family Specialists.

See also: pipeline, backfill, MD channel, XLIFF channel, Foreman,
Specialist.

## extract

The verb for stage one: converting a source document into the
standardized intermediate artifacts that the rest of the pipeline can
consume. Extraction is OPP's responsibility. The result is typically a
Markdown file, an XLIFF file, a skeleton archive, and the associated
manifests, depending on the target format requested. Choosing both
output formats produces everything in one pass.

See also: OPP, MD channel, XLIFF channel.

## translate

The verb for stage two: converting text in the source language into
text in the target language. Translation is OL's responsibility and is
performed on either the Markdown channel or the XLIFF channel. The
translation step respects shielded content so that code, math, links,
and markup are not translated as prose, and it can consult a glossary
and translation memory for consistent terminology.

See also: OL, shield/unshield, glossary, translation memory (TM).

## backfill

The verb for stage three: re-injecting translated content into the
target document format. Backfill is ORF's responsibility. On the
Markdown channel it means rendering a translated Markdown file into a
chosen output format. On the XLIFF channel it means writing translated
text back into the original document structure so that the result keeps
the source layout instead of being re-rendered from scratch.

See also: ORF, MD channel, XLIFF channel.

## MD channel

One of the two parallel paths through the pipeline, carried by
Markdown. OPP produces a Markdown file with YAML frontmatter, OL
translates it with the Markdown translator, and ORF renders it into a
target format with apply-md. The Markdown channel is text-first and
layout-tolerant: it suits web content, e-books, and cross-format
conversion, and it supports the full set of output formats. Image
references in the Markdown are handled through the images manifest.

See also: XLIFF channel, images.json, frontmatter.

## XLIFF channel

One of the two parallel paths through the pipeline, carried by XLIFF.
OPP produces an XLIFF file plus a skeleton archive, OL translates it by
filling the target elements, and ORF re-injects the translated text
into the original document with apply-xliff. The XLIFF channel is
layout-preserving: it is the right choice when the output must look
exactly like the source, including fonts, styles, and floating images.
It keeps the document in the same format it came from.

See also: MD channel, skeleton.zip.

## skeleton.zip

An archive produced by OPP for DOCX, PPTX, and EPUB inputs, alongside
the XLIFF file. It preserves the original document ZIP structure,
including the content types, styles, numbering, and media entries.
ORF's XLIFF backfill reads this archive to rebuild the document with
the translated text in place, without re-rendering styles or losing
media. The skeleton is what makes exact-layout backfill possible.

See also: XLIFF channel, manifest.json.

## manifest.json

The extraction manifest written by OPP next to its outputs. It records
metadata about the source file, such as its original name, format, and
hash, plus the extraction results: which output files were produced,
paragraph and table counts, image data, and warnings. It also points at
the skeleton archive when one exists. Downstream stages and tooling
read the manifest to understand what an extraction produced and how it
was derived.

See also: images.json, skeleton.zip.

## images.json

The image manifest produced by OPP. It lists the images found in a
source document with their MIME type, dimensions, and data size. For
DOCX floating drawings it also records whether an image is floating and
its anchor position, expressed in EMU, so that ORF can put the image
back at the same spot. ORF consumes this manifest when it injects
images on either channel, and the Markdown channel uses it for
separated image output.

See also: manifest.json, MD channel, XLIFF channel.

## shield/unshield

The pair of protective steps OL runs around the LLM translation call.
Shielding replaces content that must not be translated, such as code
blocks, math expressions, links, and HTML, with placeholders, and keeps
a map of those replacements. The LLM translates only the text that is
safe to translate. Unshielding restores the original content from the
map after translation, so code, formulas, and markup come back exactly
as they were.

See also: translate, repair pass.

## repair pass

The restoration stage OL runs after the LLM call and before unshielding.
The LLM sometimes drops, reorders, or mangles the shield placeholders,
and the repair pass fixes that by progressively restoring the markers,
from fast rule-based recovery through alignment and LLM-based
restoration to a safe fallback that appends anything still missing with
a warning. It also strips prompt-injection echoes the model may have
repeated back into the output.

See also: shield/unshield, translate.

## quality gates

A set of configurable checks OL runs after translation and repair.
They look for inline tag parity, mixed source-language terms,
out-of-bounds length ratios, locale convention leaks such as currency
or date mixing, unchanged source echoes, foreign script residue, LLM
protocol artifacts, and glossary term audit failures. Each gate emits
non-blocking warnings that travel with the output, so downstream
consumers can review quality without the translation being rejected.

See also: translate, glossary.

## FAKE_LLM

An environment switch, set as OMNI_TEST_FAKE_LLM=1, that replaces real
LLM calls with mock responses. It lets tests, CI runs, and MCP smoke
testing exercise the full pipeline with zero API cost and no API keys.
Unless real LLM keys are configured, it should always be set; unset it
only when actual translation quality is what you need to observe.

See also: FAKE_PANDOC.

## FAKE_PANDOC

An environment switch, set as OMNI_TEST_FAKE_PANDOC=1, that bypasses
the pandoc subprocess during ORF testing and substitutes a pure-Python
conversion path instead. It keeps format-conversion tests hermetic so
they do not depend on the pandoc binary being installed or behaving
identically on every machine. It matters mainly for tests that produce
DOCX, PPTX, and EPUB outputs.

See also: FAKE_LLM.

## Foreman

The orchestrating role in ORF's agent orchestration layer, distinct
from the MCP server. The Foreman receives a conversion job, assesses
its complexity, decomposes it into sub-tasks, and routes each sub-task
to the Specialist best suited to the document type. It then aggregates
the results. High-risk operations such as very large files, cloud
uploads, and manual-intervention recoveries require human approval.

See also: Specialist.

## Specialist

The per-format-family workers in ORF's agent orchestration layer. Each
Specialist handles a family of output formats: the format specialist
covers DOCX, ODT, EPUB, and PPTX; the data specialist covers XLSX, CSV,
and JSON; the markup specialist covers XML and HTML; and the email
specialist covers EML and MSG. The Foreman routes sub-tasks to the
matching Specialist and collects their results.

See also: Foreman.

## glossary

An OL feature for consistent terminology. A glossary is a mapping from
source terms to their canonical target translations, optionally with
variant spellings and a confidence value. OL loads the glossary, picks
the terms most relevant to the text being translated, and injects them
into the LLM prompt so the model uses the agreed terminology. After
translation, the terminology gate audits the output against the
glossary and flags mismatches.

See also: translation memory (TM), quality gates.

## translation memory (TM)

An OL feature for reusing past translations. Translation memory is a
store of source to target segment pairs, typically in TMX form. Before
translating a segment, OL searches the memory for similar past
segments, takes the closest matches above a similarity threshold, and
injects them into the prompt as reference context. This keeps repeated
content consistent across documents and saves API cost.

See also: glossary, translate.

## PathValidator

The security gatekeeper used by the OPP and ORF MCP servers. It decides
whether a requested file path is allowed to be touched: the path must
sit inside the configured allowlist, it must not be a symlink that
escapes that allowlist, its extension must be on the allowed list and
off the blocked executable list, and its size must stay under the
limit. Any path that fails these checks is rejected, which prevents
directory traversal and accidental access to arbitrary files.

See also: MCP.

## MCP

Model Context Protocol, the standard that lets AI agents call each
module's capabilities as tools. OPP, OL, and ORF each expose an MCP
server over stdio, with the tool counts and names documented per
module. The servers apply path allowlists through PathValidator and
support optional shared-secret authentication. Using the MCP tools is
the agent-native way to drive the pipeline step by step, passing each
step's output directory to the next.

See also: PathValidator, pipeline.

## frontmatter

The YAML block at the top of the Markdown files OPP produces. It
carries the source language, the target language, and the source
document format, and it is part of the handoff contract between OPP
and OL. OL parses the frontmatter before translating and preserves it
in the output, and it injects its own frontmatter on the Markdown
channel by default. Email backfill can also read header information
from the frontmatter.

See also: MD channel, pipeline.
