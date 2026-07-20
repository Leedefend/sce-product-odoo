"""Fail-closed empty SQL views for optional customer-supplied projections."""

import os

from odoo import models, tools


_PG_TYPES = {
    "boolean": "boolean",
    "date": "date",
    "datetime": "timestamp",
    "float": "double precision",
    "integer": "integer",
    "many2one": "integer",
    "monetary": "numeric",
}


class ScOptionalCustomerProjection(models.AbstractModel):
    _name = "sc.optional.customer.projection"
    _description = "Optional customer projection boundary"

    def _create_empty_projection_view(self):
        """Create a typed, empty view when no external customer projection exists."""
        self._cr.execute(
            """
            SELECT relation.relkind
              FROM pg_class relation
             WHERE relation.oid = to_regclass(%s)
            """,
            ("public.%s" % self._table,),
        )
        relation = self._cr.fetchone()
        if relation and relation[0] != "v":
            if os.environ.get("SC_ALLOW_EXTERNAL_PROJECTION_HANDOFF") == "1":
                return
            raise RuntimeError(
                "EXTERNAL_PROJECTION_RELATION_CONFLICT:%s:%s"
                % (self._table, relation[0])
            )
        columns = ["NULL::integer AS id"]
        for name, field in self._fields.items():
            if name == "id" or not getattr(field, "store", False):
                continue
            pg_type = _PG_TYPES.get(getattr(field, "type", ""), "varchar")
            columns.append('NULL::%s AS "%s"' % (pg_type, name.replace('"', '')))
        tools.drop_view_if_exists(self._cr, self._table)
        self._cr.execute(
            "CREATE OR REPLACE VIEW %s AS SELECT %s WHERE FALSE"
            % (self._table, ", ".join(columns))
        )
