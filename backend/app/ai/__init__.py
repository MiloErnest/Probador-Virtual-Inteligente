"""RESERVADO - Fase 2: IA generativa y Virtual Try-On.

Este paquete está intencionadamente vacío. Aquí vivirá:

    provider.py   -> Protocol `AIProvider` (contrato común)
    fashn.py      -> implementación con API externa
    local.py      -> implementación con modelo local (diffusers)
    prompts.py    -> traducción de lenguaje natural a atributos de diseño

NO se define todavía el Protocol porque aún no sabemos qué métodos y qué
parámetros necesita realmente. Una interfaz inventada antes de tener una
implementación concreta casi siempre resulta ser la interfaz equivocada.

La costura que SÍ existe ya es `settings.AI_PROVIDER`, y el hecho de que
ninguna capa superior (rutas, modelos) mencione a un proveedor concreto.
"""
