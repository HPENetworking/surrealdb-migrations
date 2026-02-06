from surrealdb_migrations.base import BaseMigration


class Migration(BaseMigration):

    async def upgrade(self, db):
        # Create a table
        await db.query("""
            DEFINE TABLE user SCHEMAFULL;
        """)

        # Define fields
        await db.query("""
            DEFINE FIELD email ON user TYPE string;
            DEFINE FIELD created_at ON user TYPE datetime;
        """)

        # Optional: add an index
        await db.query("""
            DEFINE INDEX user_email_unique ON user FIELDS email UNIQUE;
        """)

    async def downgrade(self, db):
        # Remove the table (this removes fields & indexes automatically)
        await db.query("""
            REMOVE TABLE user;
        """)
