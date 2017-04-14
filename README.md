# django-fabfile para digital-ocean

Script en fabric para configurar un servidor de digital ocean para un website implementado en django

## Configuración

Cree un archivo llamado **fabfile/secrets.json** en base a la plantilla **fabfile/secrets.json.template**

## Ejecución

```sh
fab config_server
```

## Otras tareas

* **copy_database**: importa la base de datos desde el directorio *data/dump.sql*
    ```sh
    fab copy_database
    ```
