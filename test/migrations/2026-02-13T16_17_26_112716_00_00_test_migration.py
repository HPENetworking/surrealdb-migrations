from surrealdb_migrations.base import BaseMigration


class Migration(BaseMigration):

    async def upgrade(self, db):
        await db.query("""
            CREATE user SET email = 'migration_3@example.com',
                       created_at = d'2026-02-15T00:00:00Z' ;
        """)

    async def downgrade(self, db):
        await db.query("""
            DELETE user WHERE email = 'migration_3@example.com' ;
        """)
