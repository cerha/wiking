# TODO

Developer's reminders and unfinished thoughts which didn't make it to the issue
tracker yet.  Please use the tracker if you have your own suggestions.

## Core

- Merge configuration and wsgi app definition into a single Python file.

- Handle Computer exceptions.

- Calling 'constraints' of a virtual field.

- The default check() method in base Specification class.

- Disable table layout per layout spec, not per module.

- Log LCG export warnings of interactive page rendering.  LCG collects export
  messages in the context ('context.messages()') rather than writing them to
  STDERR, so that the caller can present them to the user (localized).  Wiking
  does so for publication exports (Braille/PDF/EPUB), where they are reported
  by the test export and stored in the export record log.  Nothing reads them
  for ordinary page rendering, however, so warnings which concern the
  installation rather than the user are silently discarded -- such as a missing
  translation catalog of a gettext domain used by the page scripts.  Pass 'log'
  writing to the server log when creating the context in Handler._build() and
  friends, but keep the collecting for publication exports, where the messages
  belong to the user, not to the log.

- Keep the module caches in instances rather than in classes.
  'WikingResolver._wiking_module_class_cache',
  'WikingResolver._wiking_module_instance_cache' and
  'CachingPytisModule._cached_tables_module' are class attributes, so they are
  shared by all their instances and thus by all applications initialized in one
  process.  Only one application can be used in a process because of that,
  which doesn't matter in production, but the tests have to work around it --
  'wiking.test.Test._reset_application()' resets all three whenever a test runs
  against another application.  The cached tables module is the worst of them:
  the data caches of all modules are invalidated according to the table
  versions it keeps, so the modules of the second application never notice a
  change of the data until the reset.

## CMS

- Site initialization script with admin account creation.

- Allow extension module management to page roles.

- Delete stray attachment files after deletion triggered in database (cascade).

- Locking.

- Handle encoding of HTML attachments (to set encoding headers properly).

- Cache exported HTML for structured text content in DB.

- Show original page in attachment move form.

- Display "Privacy policy" link conditionally.

## Cleaning

- Move RssModule from CMSModule to EmbeddableCMSModule.

- Remove 'force_https_login'.
