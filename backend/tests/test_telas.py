"""Pruebas del producto: catálogo de telas, prendas subidas y pruebas de tela.

Estas pruebas recorren el circuito entero —subir una prenda, elegir una tela,
generar el resultado— contra la API real. No son pruebas del motor de imagen:
la calidad de lo que sale se juzga mirando, y eso está en PROJECT_STATUS.md.
Lo que se fija aquí es el CONTRATO y las reglas que no se deben romper sin
darse cuenta.
"""

from fastapi.testclient import TestClient

from tests.conftest import auth_headers, make_image_bytes, make_prenda_bytes, register_and_login


# --- Catálogo de telas ------------------------------------------------------


def test_el_catalogo_de_telas_es_publico(client: TestClient) -> None:
    """Leer el catálogo no exige cuenta: es el escaparate de la tienda."""
    assert client.get("/api/fabrics").status_code == 200


def test_dar_de_alta_una_tela_exige_token(client: TestClient) -> None:
    respuesta = client.post("/api/fabrics", json={"name": "Lino"})
    assert respuesta.status_code == 401


def test_la_ficha_tecnica_se_guarda_entera(auth_client: TestClient) -> None:
    """La ficha no es decoración: sin ancho de rollo no se compra tela.

    Se comprueba que todos los campos vuelven, porque es lo que separa esto de
    un escaparate bonito: la modista necesita el ancho para saber si le salen
    las piezas del patrón.
    """
    respuesta = auth_client.post(
        "/api/fabrics",
        json={
            "name": "Popelín de prueba",
            "reference": "POP-01",
            "composition": "100% algodón",
            "weight_gsm": 120,
            "width_cm": 150,
            "price_per_meter": 8.9,
            "color_name": "Blanco",
            "color_hex": "#F2F1EE",
            "pattern": "solid",
        },
    )

    assert respuesta.status_code == 201, respuesta.text
    tela = respuesta.json()
    assert tela["reference"] == "POP-01"
    assert tela["composition"] == "100% algodón"
    assert tela["weight_gsm"] == 120
    assert tela["width_cm"] == 150
    assert tela["price_per_meter"] == 8.9
    # El color se normaliza a minúsculas para que dos fichas iguales no se vean
    # distintas solo por cómo se escribieron.
    assert tela["color_hex"] == "#f2f1ee"


def test_un_color_mal_escrito_se_rechaza(auth_client: TestClient) -> None:
    """Un color inválido rompe la ficha en el navegador sin dar ninguna pista."""
    respuesta = auth_client.post(
        "/api/fabrics", json={"name": "Tela rara", "color_hex": "rojo"}
    )
    assert respuesta.status_code == 422


def test_no_se_duplican_telas_con_el_mismo_nombre(auth_client: TestClient) -> None:
    """409 y no 422: la petición es válida, lo que pasa es que ya existe."""
    auth_client.post("/api/fabrics", json={"name": "Lino crudo"})
    repetida = auth_client.post("/api/fabrics", json={"name": "Lino crudo"})
    assert repetida.status_code == 409


def test_solo_probables_excluye_las_telas_sin_mosaico(
    auth_client: TestClient, fabric_with_texture: dict
) -> None:
    """Sin mosaico no hay nada que estampar, así que no se ofrece.

    Es lo que evita que el probador enseñe telas que van a fallar al elegirlas.
    """
    auth_client.post("/api/fabrics", json={"name": "Tela sin mosaico"})

    todas = auth_client.get("/api/fabrics").json()
    probables = auth_client.get("/api/fabrics", params={"only_probable": True}).json()

    assert any(t["name"] == "Tela sin mosaico" for t in todas)
    assert all(t["texture_url"] is not None for t in probables)
    assert not any(t["name"] == "Tela sin mosaico" for t in probables)


# --- Prendas que sube el usuario --------------------------------------------


def test_subir_una_prenda_calcula_el_recorte(uploaded_garment: dict) -> None:
    """El recorte se hace al subir, no al probar.

    Cuesta lo mismo y se necesita idéntico para cada tela: calculándolo una
    vez, probar diez telas son diez multiplicaciones en lugar de diez recortes.
    """
    assert uploaded_garment["mask_url"] is not None
    assert 0.0 < uploaded_garment["mask_coverage"] < 1.0
    assert uploaded_garment["width"] == 300
    assert uploaded_garment["height"] == 400


def test_las_prendas_de_otro_responden_404(client: TestClient, user_token) -> None:
    """404 y no 403: un 403 confirmaría que el diseño existe.

    Aquí importa más que en otros sitios: el boceto de un taller es su trabajo,
    y recorriendo identificadores se podría contar la competencia.
    """
    _, token = user_token
    otro, token_otro = register_and_login(client, email="otro@example.com")

    subida = client.post(
        "/api/garment-uploads",
        data={"name": "Diseño ajeno", "kind": "photo"},
        files={"file": ("p.png", make_prenda_bytes(), "image/png")},
        headers=auth_headers(token_otro),
    )
    assert subida.status_code == 201

    ajena = client.get(
        f"/api/garment-uploads/{subida.json()['id']}", headers=auth_headers(token)
    )
    assert ajena.status_code == 404


def test_una_imagen_falsa_se_rechaza(auth_client: TestClient) -> None:
    """Se valida el CONTENIDO, no la cabecera que envía el cliente."""
    respuesta = auth_client.post(
        "/api/garment-uploads",
        data={"name": "Trampa", "kind": "photo"},
        files={"file": ("falsa.png", b"esto no es una imagen", "image/png")},
    )
    assert respuesta.status_code == 422


# --- Pruebas de tela --------------------------------------------------------


def test_probar_una_tela_de_punta_a_punta(
    auth_client: TestClient, uploaded_garment: dict, fabric_with_texture: dict
) -> None:
    """El circuito completo: prenda + tela -> imagen."""
    respuesta = auth_client.post(
        "/api/trials",
        json={
            "garment_upload_id": uploaded_garment["id"],
            "fabric_id": fabric_with_texture["id"],
        },
    )

    # 202 y no 201: el recurso existe pero todavía no tiene resultado.
    assert respuesta.status_code == 202, respuesta.text

    # El cliente de pruebas ejecuta las tareas de fondo al terminar la
    # petición, así que al consultarla ya está lista.
    prueba = auth_client.get(f"/api/trials/{respuesta.json()['id']}").json()
    assert prueba["status"] == "completed", prueba["error_message"]
    assert prueba["output_image_url"] is not None
    assert prueba["provider"] == "retexturizado-local"
    # El motor determinista no cuesta dinero, y eso se ve en la galería.
    assert prueba["tokens_used"] is None


def test_una_foto_usa_el_motor_determinista_por_defecto(
    auth_client: TestClient, uploaded_garment: dict, fabric_with_texture: dict
) -> None:
    """Una fotografía trae su propia luz: no hace falta inventarla ni pagarla."""
    prueba = auth_client.post(
        "/api/trials",
        json={
            "garment_upload_id": uploaded_garment["id"],
            "fabric_id": fabric_with_texture["id"],
        },
    ).json()
    assert prueba["method"] == "retexture"


def test_un_boceto_usa_su_propio_camino_y_no_cuesta_dinero(
    auth_client: TestClient, fabric_with_texture: dict
) -> None:
    """Un boceto se rellena conservando el trazo, no se manda a la IA.

    Al principio los bocetos iban a la IA por defecto. Se probó contra la API
    real —modelo mini, modelo completo, e `input_fidelity="high"`— y las tres
    veces devolvió una prenda DISTINTA: un boceto con cartera de botones,
    bolsillo y cuello camisero volvía convertido en una túnica lisa.

    Para un producto que promete enseñar TU diseño con otra tela, eso está mal,
    y encima se cobraba. El camino por defecto conserva el dibujo y es gratis.
    """
    boceto = auth_client.post(
        "/api/garment-uploads",
        data={"name": "Boceto", "kind": "sketch"},
        files={"file": ("b.png", make_prenda_bytes(), "image/png")},
    ).json()

    creada = auth_client.post(
        "/api/trials",
        json={"garment_upload_id": boceto["id"], "fabric_id": fabric_with_texture["id"]},
    )
    assert creada.status_code == 202
    assert creada.json()["method"] == "retexture"

    prueba = auth_client.get(f"/api/trials/{creada.json()['id']}").json()
    assert prueba["status"] == "completed", prueba["error_message"]
    assert prueba["provider"] == "retexturizado-local-boceto"
    assert prueba["tokens_used"] is None


def test_la_ia_hay_que_pedirla_y_avisa_si_no_esta_configurada(
    auth_client: TestClient, uploaded_garment: dict, fabric_with_texture: dict
) -> None:
    """El motor de IA es opt-in, y sin configurar dice qué hacer.

    Nunca cae al motor local en silencio: creer que estás usando el modelo
    cuando no lo estás es el peor fallo posible aquí, y ya se cometió una vez
    en este proyecto.
    """
    creada = auth_client.post(
        "/api/trials",
        json={
            "garment_upload_id": uploaded_garment["id"],
            "fabric_id": fabric_with_texture["id"],
            "method": "ai",
        },
    )
    assert creada.status_code == 202
    assert creada.json()["method"] == "ai"

    prueba = auth_client.get(f"/api/trials/{creada.json()['id']}").json()
    assert prueba["status"] == "failed"
    assert "AI_PROVIDER" in prueba["error_message"]


def test_una_tela_sin_mosaico_no_se_puede_estampar(
    auth_client: TestClient, uploaded_garment: dict
) -> None:
    """Se rechaza al crear la prueba, no al procesarla.

    Fallar pronto le ahorra al usuario esperar un sondeo para descubrir algo
    que se sabía desde el principio.
    """
    tela = auth_client.post("/api/fabrics", json={"name": "Sin mosaico"}).json()

    respuesta = auth_client.post(
        "/api/trials",
        json={"garment_upload_id": uploaded_garment["id"], "fabric_id": tela["id"]},
    )
    assert respuesta.status_code == 422
    assert "mosaico" in respuesta.json()["detail"]


def test_comparar_varias_telas_sobre_la_misma_prenda(
    auth_client: TestClient, uploaded_garment: dict
) -> None:
    """La comparación lado a lado: todas las pruebas de un mismo diseño.

    Y aquí se ve por qué el motor determinista es el principal: las tres
    imágenes salen de la misma prenda con la misma luz, así que lo único que
    cambia entre ellas es la tela. Con un motor generativo, cada una tendría un
    corte distinto y la comparación no significaría nada.
    """
    telas = []
    for i, color in enumerate(("navy", "tan", "olive")):
        creada = auth_client.post("/api/fabrics", json={"name": f"Tela {i}"}).json()
        auth_client.post(
            f"/api/fabrics/{creada['id']}/texture",
            files={"file": ("t.png", make_image_bytes(64, 64, color), "image/png")},
        )
        telas.append(creada["id"])

    for fabric_id in telas:
        auth_client.post(
            "/api/trials",
            json={"garment_upload_id": uploaded_garment["id"], "fabric_id": fabric_id},
        )

    de_esta_prenda = auth_client.get(
        "/api/trials", params={"garment_upload_id": uploaded_garment["id"]}
    ).json()

    assert len(de_esta_prenda) == 3
    assert all(p["status"] == "completed" for p in de_esta_prenda)
    assert {p["fabric_id"] for p in de_esta_prenda} == set(telas)


def test_borrar_la_prenda_se_lleva_sus_pruebas(
    auth_client: TestClient, uploaded_garment: dict, fabric_with_texture: dict
) -> None:
    """Las pruebas cuelgan de la prenda: sin ella no significan nada."""
    auth_client.post(
        "/api/trials",
        json={
            "garment_upload_id": uploaded_garment["id"],
            "fabric_id": fabric_with_texture["id"],
        },
    )

    borrada = auth_client.delete(f"/api/garment-uploads/{uploaded_garment['id']}")
    assert borrada.status_code == 200
    assert auth_client.get("/api/trials").json() == []


def test_las_pruebas_de_otro_responden_404(client: TestClient, user_token) -> None:
    _, token = user_token
    _, token_otro = register_and_login(client, email="ajeno@example.com")

    tela = client.post(
        "/api/fabrics", json={"name": "Tela ajena"}, headers=auth_headers(token_otro)
    ).json()
    client.post(
        f"/api/fabrics/{tela['id']}/texture",
        files={"file": ("t.png", make_image_bytes(64, 64, "navy"), "image/png")},
        headers=auth_headers(token_otro),
    )
    prenda = client.post(
        "/api/garment-uploads",
        data={"name": "Suya", "kind": "photo"},
        files={"file": ("p.png", make_prenda_bytes(), "image/png")},
        headers=auth_headers(token_otro),
    ).json()
    prueba = client.post(
        "/api/trials",
        json={"garment_upload_id": prenda["id"], "fabric_id": tela["id"]},
        headers=auth_headers(token_otro),
    ).json()

    ajena = client.get(f"/api/trials/{prueba['id']}", headers=auth_headers(token))
    assert ajena.status_code == 404


def test_los_endpoints_del_producto_exigen_token(client: TestClient) -> None:
    """Inventario explícito de lo que exige cuenta.

    Escrito como lista para que quitarle la protección a uno rompa la suite en
    vez de pasar inadvertido.
    """
    protegidos = [
        ("GET", "/api/garment-uploads"),
        ("POST", "/api/garment-uploads"),
        ("GET", "/api/garment-uploads/1"),
        ("DELETE", "/api/garment-uploads/1"),
        ("GET", "/api/trials"),
        ("POST", "/api/trials"),
        ("GET", "/api/trials/1"),
        ("POST", "/api/fabrics"),
        ("POST", "/api/fabrics/1/texture"),
    ]
    for metodo, ruta in protegidos:
        respuesta = client.request(metodo, ruta)
        assert respuesta.status_code == 401, f"{metodo} {ruta} no exige autenticación"
