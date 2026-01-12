from imageset_generator.app import app


def test_generate_preview_endpoint_returns_yaml():
    app.testing = True
    client = app.test_client()

    payload = {
        "ocp_versions": ["4.16"],
        "ocp_channel": "stable-4.16",
        "operators": [
            {
                "name": "cluster-logging",
                "catalog": "registry.redhat.io/redhat/redhat-operator-index",
                "minVersion": "5.8.0",
                "maxVersion": "5.8.1",
            }
        ],
        "additional_images": ["registry.redhat.io/ubi8/ubi:latest"],
    }

    response = client.post("/api/generate/preview", json=payload)
    assert response.status_code == 200
    data = response.get_json()
    assert data["success"] is True
    assert "cluster-logging" in data["yaml"]
