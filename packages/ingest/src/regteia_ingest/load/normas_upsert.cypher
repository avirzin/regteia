// Upsert norms backed by an upstream file. Null values in `row` remove the property.
UNWIND $rows AS row
MERGE (n:Norma {id: row.id})
SET n += row, n.externo = false
RETURN count(n) AS n
