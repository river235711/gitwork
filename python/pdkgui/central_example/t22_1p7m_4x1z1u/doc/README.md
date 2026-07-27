# PDF tree for this process

The DOC tab looks the PDFs of a document up here, using the two first fields of
each `DOC.txt` line (`<Doc. No.>|<Doc ID>|<Title>`):

```
<CENTRAL>/<DESIGN>/doc/<Doc. No.>/<Doc ID>/*.pdf
```

So the line

```
DRCCommandFile|T-N22-CL-DR-001-C1|TSMC 22 NM ... DRC COMMAND FILE (CALIBRE) (...)
```

is served from

```
<CENTRAL>/t22_1p7m_4x1z1u/doc/DRCCommandFile/T-N22-CL-DR-001-C1/
    TN22CLDR001C1_1_8a.pdf
    N22_DRC_Switch_UserGuide_V18a.pdf
    ...
```

Only `*.pdf` is listed, sorted by name; clicking one opens it in a PDF viewer.
Adding a document = add its line to `DOC.txt` and drop the PDFs in the matching
directory -- no code change.

If the PDF tree has to live on a different share, point env `PDKGUI_DOC_ROOT` at
that base (the `<DESIGN>/doc/...` structure below it stays the same).
