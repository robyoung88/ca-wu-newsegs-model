from typing import Any

import sqlalchemy as sa

def generic_snapshot_entity(
    engine: sa.Engine,
    metadata: sa.MetaData,
    root_table_name: str,
    root_id: int,
    snapshot_label: str,
    project_id: int
) -> int:
    """
    Introspects schema dependencies starting from root_table_name and
    automatically creates a snapshot of all linked child and junction records.
    """
    with engine.begin() as conn:
        # Create the master Snapshot entry
        snapshots = metadata.tables['snapshots']
        res = conn.execute(
            snapshots
            .insert()
            .values(
                project_id = project_id,
                label = snapshot_label
            )
        )
        if not res or not res.inserted_primary_key:
            raise ValueError('Snapshot has not been created')
        snapshot_id = res.inserted_primary_key[0]

        # Collect all active tables sorted topologically by foreign key dependencies
        # (Parents come before children)
        sorted_tables = metadata.sorted_tables

        # Track IDs that belong to this snapshot to filter child queries
        # Map format: { 'table_name': set(primary_key_ids) }
        collected_ids: dict[str, set] = {}

        # Traversal: Find all primary keys belonging to this root instance
        # Map all foreign key dependencies
        ignore_table = lambda x: x.name.startswith('snapshot_') or x.name in ('snapshots', 'users', 'sessions', 'groups')
        fk_deps = {}
        for table in sorted_tables:
            if ignore_table(table):
                continue
            for fk in table.foreign_key_constraints:
                current_deps = fk_deps.get(table.name, set())
                current_deps.add(fk.referred_table.name)
                fk_deps[table.name] = current_deps

        # Reverse these dependencies
        has_children = {}
        for k, v in fk_deps.items():
            for fk in v:
                current_children = has_children.get(fk, set())
                current_children.add(k)
                has_children[fk] = current_children

        if root_table_name in has_children.keys():
            # Now work through the dependencies until we have a list of all foreign keys
            tables_to_search = [root_table_name]
            while len(tables_to_search):
                table_name = tables_to_search.pop(0)
                table = metadata.tables.get(table_name)
                if table is None:
                    continue

                pk_cols = list(table.primary_key.columns)

                known_ids = collected_ids.get(table.name, set())
                n_known_ids = len(known_ids)

                if table.name == root_table_name:
                    pk_col = pk_cols[0]
                    stmt = sa.select(table).where(pk_col == root_id)
                else:
                    # For children or junction tables, filter the table down using parent IDs
                    fk_conditions = []
                    for fk in table.foreign_key_constraints:
                        parent_table = fk.referred_table.name
                        if parent_table in collected_ids:
                            child_fk_col = list(fk.columns)[0]
                            fk_conditions.append(child_fk_col.in_(collected_ids[parent_table]))

                    pk_conditions = []

                    if n_known_ids > 0:
                        if len(pk_cols) == 1:
                            pk_conditions.append(pk_cols[0].in_(collected_ids.get(table.name, set())))
                        else:
                            pk_conditions.extend([
                                pk_cols[i].in_([
                                    x[i] for x in collected_ids.get(table.name, set())
                                ]) for i in range(len(pk_cols))
                            ])

                    stmt = sa.select(table).where(sa.or_(*fk_conditions, *pk_conditions))

                rows = conn.execute(stmt).fetchall()

                if len(rows) > n_known_ids:
                    # We have an update to the collected ids for this table
                    if len(pk_cols) == 1:
                        known_ids.update(set({row._mapping[pk_cols[0].name] for row in rows}))
                    else:
                        known_ids.update(set({
                            tuple(row._mapping[c.name] for c in pk_cols) for row in rows
                        }))
                    collected_ids[table.name] = known_ids

                    # Update the tables to search with any dependents of this table
                    child_table_names = has_children.get(table_name, set())
                    for nm in child_table_names:
                        if nm in tables_to_search:
                            tables_to_search.remove(nm)
                        tables_to_search.append(nm)

                if rows:
                    for fk in table.foreign_key_constraints:
                        # If there are any foreign keys, update with the currently selected keys
                        parent_table = fk.referred_table.name
                        current_ids = collected_ids.get(parent_table, set())
                        n_ids = len(current_ids)
                        child_fk_col = list(fk.columns)[0]
                        new_ids = set({row._mapping[child_fk_col] for row in rows})
                        current_ids.update(new_ids)
                        if len(current_ids) > n_ids:
                            collected_ids[parent_table] = current_ids
                            if parent_table in tables_to_search:
                                tables_to_search.remove(parent_table)
                            tables_to_search.append(parent_table)
                            if has_children.get(parent_table):
                                for child in has_children.get(parent_table, set()):
                                    if child in tables_to_search:
                                        tables_to_search.remove(child)
                                    tables_to_search.append(child)

        # Copy: Insert matching records into `snapshot_<table_name>` tables
        for table in sorted_tables:
            if table.name in collected_ids and collected_ids[table.name]:
                snapshot_table_name = f'snapshot_{table.name}'
                if snapshot_table_name not in metadata.tables:
                    continue

                snap_table = metadata.tables[snapshot_table_name]

                # Fetch original rows
                pk_cols = list(table.primary_key.columns)
                if len(pk_cols) == 1:
                    stmt = (
                        sa.select(table)
                        .where(pk_cols[0].in_(collected_ids[table.name]))
                    )
                else:
                    # Junction table filtering
                    stmt = sa.select(table)

                rows = conn.execute(stmt).mappings().fetchall()

                # Bulk insert into snapshot table with snapshot_id attached
                records_to_insert = []
                for row in rows:
                    record = dict(row)
                    record['snapshot_id'] = snapshot_id
                    records_to_insert.append(record)

                if records_to_insert:
                    conn.execute(snap_table.insert(), records_to_insert)

        # Ensure project retention: If a Project has snapshots, it should be marked for retention
        projects = metadata.tables.get('projects')
        if projects is not None and 'retain' in projects.c:
            conn.execute(
                projects.update()
                .where(projects.c.project_id == project_id)
                .values(retain=True)
            )

    return snapshot_id

def generic_restore_snapshot(
    engine: sa.Engine,
    metadata: sa.MetaData,
    snapshot_id: int
) -> dict[str, int]:
    """
    Introspects snapshot tables, recreates nested entity structures inside active tables
    and dynamically re-maps foreign key references for all nested dependencies.
    """
    # Key mapping registry: { ('table_name', old_id): new_id }
    id_map: dict[tuple, Any] = {}

    with engine.begin() as conn:
        for table in metadata.sorted_tables:
            # Skip non-target tables
            if table.name.startswith('snapshot_') or table.name in ('snapshots', 'projects', 'users'):
                continue

            snap_table_name = f'snapshot_{table.name}'
            if snap_table_name not in metadata.tables:
                continue

            snap_table = metadata.tables[snap_table_name]

            # Fetch all snapshotted records for this specific snapshot_id
            snap_rows = conn.execute(
                sa.select(snap_table).where(snap_table.c.snapshot_id == snapshot_id)
            ).mappings().fetchall()

            for row in snap_rows:
                record = dict(row)
                # Remove snapshot_id metadata
                record.pop('snapshot_id', None)

                # Dynamically update Foreign Keys pointing to previously restored parents
                for fk in table.foreign_key_constraints:
                    parent_table_name = fk.referred_table.name
                    child_fk_col = list(fk.columns)[0].name
                    old_parent_id = record.get(child_fk_col)

                    # Replace old parent ID with newly generated restored parent ID
                    if (parent_table_name, old_parent_id) in id_map:
                        record[child_fk_col] = id_map[(parent_table_name, old_parent_id)]

                # Check if table uses auto-increment surrogate PK or composite key
                pk_cols = [c.name for c in table.primary_key.columns]
                is_single_autoincrement_pk = len(pk_cols) == 1 and table.columns[pk_cols[0]].autoincrement

                if is_single_autoincrement_pk:
                    old_pk_val = record.pop(pk_cols[0], None)
                    res = conn.execute(table.insert().values(**record))
                    new_pk_val = res.inserted_primary_key[0]
                    # Map old primary key to new primary key for child references
                    id_map[(table.name, old_pk_val)] = new_pk_val
                else:
                    # Junction table or fixed key insertion
                    conn.execute(table.insert().values(**record))
    return id_map