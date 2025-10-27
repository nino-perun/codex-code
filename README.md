## Trip page generator

This repository contains a small utility that renders HTML trip pages using
database content. Once your PostgreSQL database is configured (see
`config/database.ini` for the expected settings), you can render a page by
providing both the page name and the snippet template filename:

```
python -m src.generator turkey.html snippet.html
```

The command looks up the `turkey.html.skel` file in the `templates/` directory,
renders each related snippet using `templates/snippet.html` (or the template you
provide), and writes the final HTML to `turkey.html` in the working directory.
