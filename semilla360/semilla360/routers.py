class DatabaseRouter:
    def db_for_read(self, model, **hints):
        # Verifica si el modelo pertenece a la aplicación 'importaciones'
        if model._meta.app_label == 'importaciones':
            # Verifica si el hint 'database' está definido (lo pasaremos manualmente)
            return hints.get('database')
        # Si el modelo no es de 'importaciones', usa 'default'
        return 'default'

    def db_for_write(self, model, **hints):
        # Prohibe escritura en bases de datos de SQL Server, solo permite en 'default'
        return 'default' if model._meta.app_label != 'importaciones' else None

    def allow_migrate(self, db, app_label, model_name=None, **hints):
        # Impide migraciones en las bases de datos de solo lectura
        return db == 'default'
