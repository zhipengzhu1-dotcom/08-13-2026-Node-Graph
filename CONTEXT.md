# Words we use

This is the agreed word list for the SOP Graph Viewer. Use these words. Do not use synonyms.

Write in ASD-STE100 Simplified Technical English. Short sentences. Active voice. One idea per sentence.

## The organisation

**Example Labs Corp.** A fictional testing laboratory. It works under state regulatory rules and to ISO 17025. All document titles in this repository are randomly generated stand-ins.

**QMS.** The quality management system. The set of controlled documents that says how the laboratory works.

## Document classes

**SOP.** A standard operating procedure. Numbered `EXL-SOP01` to `EXL-SOP60`. It says how to do a task.

**Form.** A blank record sheet. Numbered `EXL-FM01` to `EXL-FM86`. A person fills it in and it becomes a record.

**Analytical procedure.** A test method. Numbered `EXL-AP01` to `EXL-AP26`. Also called a method.

**Document.** Any of the three above. There are 162 active documents.

**Tracking log.** A form that lists documents of one class. `EXL-FM11` lists SOPs. `EXL-FM12` and `EXL-FM13` list methods. `EXL-FM14` lists forms. The tracking logs are the laboratory's own index.

## Numbering

**Document number.** The identifier without the revision. Example: `EXL-SOP10`.

**Revision.** The two digits after the document number. Example: `-03`.

**Full number.** The document number and the revision together. Example: `EXL-SOP10-03`.

The full number changes at each revision. So the full number is not a stable identifier. Use the document number as the identity. Hold the revision as a property.

**Live.** The document is the current version and is in use.

**Superseded.** A newer revision replaced this one. Superseded files are moved to a `_superseded/` folder. They are kept, not deleted.

## The graph

**Node.** One thing in the graph. There are four node types: SOP, form, analytical procedure, instrument.

**Instrument.** A machine in the laboratory. The autoclave, the balance, the pH meter, the GC-MS. An instrument is a node but it is not a document.

**Link.** A connection between two nodes.

**Extracted link.** A link found in the text of a document. It draws as a solid line.

**Asserted link.** A link a person added by hand, because they know it is true and the document does not say so. It draws as a dotted line.

**Correction file.** The file that holds asserted links and instrument name joins. The documents are never changed.

**Work list.** The set of asserted links. Each one is an SOP that does not declare a real dependency. The work list is what must be written into the documents at their next revision.

## The program

**Viewer.** The program that shows the graph. It runs on Windows in the laboratory. It reads the documents. It never writes them.

**Source of truth.** The place that holds the correct document text. This is the shared document folders, not the viewer.

**Owner.** The person who can edit the correction file. One person only.

**Analyst.** A person who uses the viewer to read. They cannot edit the correction file.
