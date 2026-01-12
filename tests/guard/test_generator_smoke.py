import yaml

from generator import ImageSetGenerator


def test_generator_smoke_builds_expected_config():
    generator = ImageSetGenerator()
    generator.add_ocp_versions(
        versions=["4.16.0", "4.16.1"],
        channel="stable-4.16",
    )

    channels = {"cluster-logging": {"stable-5.8"}}
    newest_channel = {"cluster-logging": "stable-5.8"}
    generator.add_operators(
        operators=[
            {
                "name": "cluster-logging",
                "catalog": "registry.redhat.io/redhat/redhat-operator-index",
                "minVersion": "5.8.0",
                "maxVersion": "5.8.1",
            }
        ],
        catalog="registry.redhat.io/redhat/redhat-operator-index",
        channels=channels,
        ocp_version="4.16",
        newest_channel=newest_channel,
    )
    generator.add_additional_images(["registry.redhat.io/ubi8/ubi:latest"])

    config = generator.config
    platform_channels = config["spec"]["mirror"]["platform"]["channels"]
    assert platform_channels[0]["minVersion"] == "4.16.0"
    assert platform_channels[0]["maxVersion"] == "4.16.1"

    operator_config = config["spec"]["mirror"]["operators"][0]
    assert (
        operator_config["catalog"]
        == "registry.redhat.io/redhat/redhat-operator-index:v4.16"
    )
    package = operator_config["packages"][0]
    assert package["name"] == "cluster-logging"
    assert package["defaultChannel"] == "stable-5.8"
    assert package["channels"] == [{"name": "stable-5.8"}]

    yaml_output = generator.generate_yaml()
    body = yaml.safe_load("\n".join(line for line in yaml_output.splitlines() if not line.startswith("#")))
    assert body["mirror"]["additionalImages"][0]["name"] == "registry.redhat.io/ubi8/ubi:latest"


def test_generator_uses_operator_channel_when_mapping_missing():
    generator = ImageSetGenerator()
    generator.add_operators(
        operators=[
            {
                "name": "cluster-logging",
                "channel": "stable-5.8",
            }
        ],
        catalog="registry.redhat.io/redhat/redhat-operator-index",
    )

    operator_config = generator.config["spec"]["mirror"]["operators"][0]
    package = operator_config["packages"][0]
    assert package["channels"] == [{"name": "stable-5.8"}]
    assert package["defaultChannel"] == "stable-5.8"
