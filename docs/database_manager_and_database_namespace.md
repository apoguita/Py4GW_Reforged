# Database Manager And Database Namespace

This document describes the current database architecture used by `Py4GWCoreLib`:

- `DBMgr`: the low-level SQLite database manager
- `Database`: the namespace used by project code
- `Database.Account`: account-focused helpers for `Py4GW_Accounts`

It reflects the current direct-database-access implementation.

## Overview

The database stack is intentionally split into two layers:

1. `DBMgr`
   - generic database lifecycle and CRUD operations
   - bootstrap and catalog management
   - SQL generation for common operations

2. project subclasses exposed through `Database`
   - project-specific tables
   - project-specific helper methods
   - no raw SQL required from normal callers

In normal usage, project code should prefer:

```python
from Py4GWCoreLib import Database

accounts = Database.Account()
```

and only drop to `DBMgr` when generic database operations are actually needed.

## DBMgr

Source:

- [Py4GWCoreLib/database_src/DBMgr.py](../Py4GW_python_files/Py4GWCoreLib/database_src/DBMgr.py)

### Purpose

`DBMgr` is the central SQLite manager for the project.

It is responsible for:

- locating the project `data/` directory
- creating and maintaining the PRIMARY internal database
- registering named databases in the PRIMARY catalog
- discovering setup scripts in `data/db_setup/`
- creating database files from setup SQL
- providing generic CRUD and maintenance APIs

### Database naming model

`DBMgr` works by database alias, not by raw filesystem path.

Example:

```python
db = DBMgr('Py4GW_Accounts')
```

That alias is resolved through the PRIMARY catalog database.

### Bootstrap model

On first use, `DBMgr` bootstraps:

- the projects path
- the `data/` folder
- the PRIMARY database
- setup-defined databases discovered from `data/db_setup/*.sql`

This means project databases can be created automatically from SQL setup scripts without manual runtime initialization code.

### Generic API categories

`DBMgr` exposes generic operations such as:

- table creation and schema inspection
- `Insert`, `Update`, `Delete`, `Select`
- `Merge`
- `Execute` for raw SQL escape-hatch use
- transactions
- backup/export/import/vacuum

The intent is:

- app code should not write SQL for normal CRUD
- app code should provide table names, fields, and values

## Database Namespace

Source:

- [Py4GWCoreLib/Database.py](../Py4GW_python_files/Py4GWCoreLib/Database.py)

### Purpose

`Database` is not a database engine by itself.

It is a namespace facade that exposes the project database classes in one place:

```python
from .database_src import Account, DBMgr


class Database:
    DBMgr = DBMgr
    Account = Account
```

That allows code such as:

```python
Database.DBMgr(...)
Database.Account()
```

### Why it exists

The goal is organization:

- one top-level access point
- clear project-specific subclasses
- no need for callers to know the internal `database_src` package layout

## Database.Account

Source:

- [Py4GWCoreLib/database_src/Account.py](../Py4GW_python_files/Py4GWCoreLib/database_src/Account.py)

### Purpose

`Account` is the project-focused subclass for the `Py4GW_Accounts` database.

It wraps account-domain tables and operations:

- `Account`
- `Character`
- `Team`
- `Team_Name`

### Binding

`Account` subclasses `DBMgr` and binds itself to:

```python
DATABASE_NAME = 'Py4GW_Accounts'
```

So:

```python
Database.Account()
```

is already attached to the accounts database.

### Main responsibilities

`Account` provides typed helpers for:

- account lookup by email
- account key lookup
- account create/update/delete
- character create/update/delete
- character lookup by account or name
- team-name create/update/delete
- team membership create/update/delete

### Important method

The key lookup method used across the project is:

```python
GetAccountKey(email)
```

This resolves the account primary key from an immutable email.

## Recommended Usage

### Generic database work

Use `Database.DBMgr` only when the work is generic and not tied to one project database subclass.

### Accounts database

Use `Database.Account()` when working with:

- account login/profile data
- characters
- teams

## Design Notes

- `DBMgr` is the generic authority.
- `Database` is the project namespace.
- `Account` is the project subclass.
- `Account` is keyed around the accounts database domain.
