# Graph model

`graph.json` is a node-link graph: `nodes`, `links`, plus `communities`, `analysis`, `concepts`, `tours`. Links are stored under `links`, as in NetworkX node-link JSON.

## Nodes

| Type | Meaning | Id pattern |
|---|---|---|
| `file` | a source, markup, SQL or config file | `file:<path>` |
| `module` | a directory | `module:<dir>` |
| `class` | class, interface, enum, record, React class | `class:<path>#<Name>` |
| `function` | function, method, arrow function, React component (`kind: component`) | `fn:<path>#<Owner.name>` |
| `endpoint` | REST mapping or UI route | `endpoint:<VERB> <path>@<file>` |
| `datastore` | SQL table, entity table, browser storage key | `datastore:table:<name>`, `datastore:storage:<api>:<key>` |
| `external` | npm or Maven package, HTTP host, CDN script | `external:<name>` |
| `config` | environment variable | `config:env:<NAME>` |

Every node has `name`, `file`, `line`, `lang`, `kind`, `layer`, `tags`, `summary` (empty until enriched), `degree` (links other than `contains`) and, for core types, `community`.

Layers: `ui`, `api`, `service`, `data`, `config`, `integration`, `core`, `test`, `external`. They come from annotations (`@RestController`, `@Service`, `@Repository`, `@Entity`, `@Configuration`) and from path names.

## Links

| Type | From -> to |
|---|---|
| `contains` | module -> file, file -> class or function, class -> method |
| `imports` | file -> file or external package |
| `calls` | function -> function |
| `uses` | function or class -> class or component (type use, JSX, config) |
| `extends`, `implements` | class -> class |
| `exposes` | class or method -> endpoint, endpoint -> handler or component |
| `reads`, `writes` | function or file -> datastore |
| `maps_to` | entity class -> table |
| `manages` | Spring Data repository -> entity |
| `references` | table -> table (foreign key) |
| `loads` | HTML page -> script, stylesheet or CDN |
| `fetches` | function -> external host |
| `depends_on` | build file -> external package |

Each link has `confidence` (EXTRACTED, INFERRED, AMBIGUOUS) and `evidence` (`path:line`).

## Analysis block

`hubs` (most connected), `import_cycles`, `entry_points`, `orphan_files`, `duplicate_names` (same function or class name in several files), `similar_lists` (string lists in different files that overlap by 60 percent or more: identical copies or near-copies with different members), `surprising_links` (links between otherwise separate communities), `layers`.

Communities are found by weighted label propagation over the links (containment, extends and foreign keys weigh more; AMBIGUOUS weighs less), and tiny groups are merged into their strongest neighbour. They are labelled by the dominant directory and the top node, and can be renamed during enrichment.

## What is not extracted

Types of local variables beyond simple declarations, calls through reflection or lambdas stored in variables, generics resolution, SQL built from strings, dependency injection by qualifier, code in templates or generated at build time, and anything outside the supported languages.
