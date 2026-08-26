"""El registro de modelos debe ser portable: clonar o mover el proyecto no puede
romper la carga del artefacto activo.

Antes se guardaba la ruta absoluta de la máquina donde se entrenó, así que al
mover la carpeta `load_active_artifact()` fallaba con FileNotFoundError.
"""
import pytest

from screener.models import registry


@pytest.fixture
def models_dir(tmp_path, monkeypatch):
    d = tmp_path / "models"
    d.mkdir()
    monkeypatch.setattr(registry.settings, "models_dir", d)
    return d


def test_resuelve_por_nombre_en_el_models_dir_actual(models_dir):
    artefacto = models_dir / "tactical_20260615_140800.joblib"
    artefacto.touch()

    assert registry.resolve_model_path(artefacto.name) == artefacto


def test_registro_antiguo_con_ruta_absoluta_de_otra_maquina(models_dir):
    """Compatibilidad hacia atrás: solo importa el nombre del fichero."""
    artefacto = models_dir / "tactical_20260615_140800.joblib"
    artefacto.touch()
    legacy = r"C:\Users\otra-maquina\Proyectos\Stock\models\tactical_20260615_140800.joblib"

    assert registry.resolve_model_path(legacy) == artefacto


def test_ruta_absoluta_existente_se_respeta(tmp_path, models_dir):
    """Si la ruta guardada sigue siendo válida se usa tal cual."""
    externo = tmp_path / "otro" / "tactical_20260615_140800.joblib"
    externo.parent.mkdir()
    externo.touch()

    assert registry.resolve_model_path(str(externo)) == externo


def test_artefacto_ausente_devuelve_ruta_en_models_dir(models_dir):
    """No existe en ninguna parte: se devuelve el candidato para que quien
    llama emita un error accionable ('vuelve a ejecutar train')."""
    faltante = registry.resolve_model_path("tactical_inexistente.joblib")

    assert faltante == models_dir / "tactical_inexistente.joblib"
    assert not faltante.exists()


def test_un_modelo_nuevo_invalida_la_cache(models_dir, monkeypatch):
    """La API no puede servir el modelo viejo tras un reentrenamiento externo.

    Si `train` corre en el CLI o en la tarea programada, el proceso de la API
    no ejecuta `register_model` y por tanto nunca limpia su caché. Al indexarla
    por el fichero del registro activo, la siguiente llamada ve el modelo nuevo.
    """
    import joblib

    viejo = models_dir / "tactical_viejo.joblib"
    nuevo = models_dir / "tactical_nuevo.joblib"
    joblib.dump({"marca": "viejo"}, viejo)
    joblib.dump({"marca": "nuevo"}, nuevo)

    activo = {"model_path": viejo.name}
    monkeypatch.setattr(
        registry, "get_active_record", lambda: type("R", (), activo)()
    )

    assert registry.load_active_artifact()["marca"] == "viejo"

    activo["model_path"] = nuevo.name  # otro proceso reentrenó y registró

    assert registry.load_active_artifact()["marca"] == "nuevo"
