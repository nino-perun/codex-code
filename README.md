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

## GUI data manager

To inspect or edit the records in `tlinq.trip_page` and `tlinq.trip_snippet`,
run the Tkinter-based GUI manager:

```
python -m src.gui_manager
```

The window displays a master list of trip pages on the left. Selecting a page
shows its associated snippets on the right. Use **Add Page** / **Save Page** to
create or update trip pages, and **Add Snippet** / **Save Snippet** for
snippets. The utility only supports creating and editing records; deleting rows
is intentionally not available.
