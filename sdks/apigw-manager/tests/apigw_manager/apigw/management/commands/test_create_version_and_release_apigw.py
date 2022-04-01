# -*- coding: utf-8 -*-
"""
 * TencentBlueKing is pleased to support the open source community by making 蓝鲸智云-蓝鲸 PaaS 平台(BlueKing-PaaS) available.
 * Copyright (C) 2017-2021 THL A29 Limited, a Tencent company. All rights reserved.
 * Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at http://opensource.org/licenses/MIT
 * Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
 * an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
 * specific language governing permissions and limitations under the License.
"""
from datetime import datetime

import pytest
import yaml
from packaging.version import parse as parse_version

from apigw_manager.apigw.management.commands.create_version_and_release_apigw import Command


@pytest.fixture()
def default_command_flags(definition_file):
    return {
        "define": [],
        "file": str(definition_file),
        "namespace": "",
    }


@pytest.fixture()
def fetcher(mocker):
    return mocker.MagicMock()


@pytest.fixture()
def releaser(mocker):
    return mocker.MagicMock()


@pytest.fixture()
def resource_sync_manager(mocker):
    manager = mocker.MagicMock()
    manager.get.return_value = {}
    return manager


@pytest.fixture()
def datetime_now():
    return datetime.now()


@pytest.fixture()
def command(mocker, fetcher, releaser, resource_sync_manager, datetime_now):
    command = Command()
    command.Fetcher = mocker.MagicMock(return_value=fetcher)
    command.Releaser = mocker.MagicMock(return_value=releaser)
    command.ResourceSignatureManager = mocker.MagicMock(return_value=resource_sync_manager)
    command.now_func = mocker.MagicMock(return_value=datetime_now)
    return command


@pytest.mark.parametrize(
    "version, title, expected",
    [
        (None, None, "None"),
        ("1.0.0", None, "1.0.0"),
        (None, "1.0.0", "1.0.0"),
        ("1.0.1", "1.0.0", "1.0.1"),
        ("v1.0.0", None, "1.0.0"),
        (None, "v1.0.0", "1.0.0"),
    ],
)
def test_get_version_from_definition(command, version, title, expected):
    result = command.get_version_from_definition(
        {
            "version": version,
            "title": title,
        }
    )

    assert str(result) == expected


@pytest.mark.parametrize(
    "resource_version, expected",
    [
        (None, "None"),
        ({"version": "1.0.0"}, "1.0.0"),
        ({"version": "v1.0.0"}, "1.0.0"),
        ({"title": "1.0.0"}, "1.0.0"),
        ({"title": "v1.0.0"}, "1.0.0"),
    ],
)
def test_get_version_from_resource_version(command, resource_version, expected):
    result = command.get_version_from_resource_version(resource_version)

    assert str(result) == expected


@pytest.mark.parametrize(
    # This is a parametrize decorator. It allows you to create multiple test cases with the same
    # method name.
    "current, latest, expected_current_version, expected_latest_version",
    [
        (None, None, "0.0.1", "?"),
        (None, "1.0.0", "1.0.0+{build_metadata}", "1.0.0"),
        ("1.0.1", "1.0.0", "1.0.1", "1.0.0"),
        ("1.0.1", None, "1.0.1", "?"),
    ],
)
def test_fix_version(command, current, latest, expected_current_version, expected_latest_version, datetime_now):
    current_version, latest_version = command.fix_version(
        current and parse_version(current),
        latest and parse_version(latest),
    )

    build_metadata = datetime_now.strftime("%Y%m%d%H%M%S")
    assert str(current_version) == expected_current_version.format(build_metadata=build_metadata)
    assert str(latest_version) == expected_latest_version.format(build_metadata=build_metadata)


class TestHandle:
    def test_handle_version_not_change(
        self,
        command,
        fetcher,
        releaser,
        faker,
        definition_file,
        resource_sync_manager,
        default_command_flags,
    ):
        version = "1.0.0"
        definition_file.write(yaml.dump({"version": version}))
        stage = faker.pystr()
        resource_version_name = faker.pystr()
        fetcher.latest_resource_version.return_value = {
            "version": version,
            "name": resource_version_name,
        }
        releaser.release.return_value = {
            "resource_version_name": resource_version_name,
            "resource_version_title": faker.pystr(),
            "stage_names": [stage],
        }
        resource_sync_manager.is_dirty.return_value = False

        command.handle(stage=stage, **default_command_flags)

        releaser.create_resource_version.assert_not_called()
        releaser.release.assert_called_once_with(
            resource_version_name=resource_version_name,
            stage_names=stage,
        )

    def test_handle_version_not_change_but_dirty(
        self,
        command,
        fetcher,
        releaser,
        faker,
        definition_file,
        resource_sync_manager,
        default_command_flags,
    ):
        version = "1.0.0"
        definition_file.write(yaml.dump({"version": version}))
        stage = faker.pystr()
        resource_version_name = faker.pystr()
        fetcher.latest_resource_version.return_value = {
            "version": version,
            "name": resource_version_name,
        }
        releaser.release.return_value = {
            "resource_version_name": resource_version_name,
            "resource_version_title": faker.pystr(),
            "stage_names": [stage],
        }
        releaser.create_resource_version.return_value = {"name": resource_version_name}
        resource_sync_manager.is_dirty.return_value = True

        command.handle(stage=stage, **default_command_flags)

        releaser.create_resource_version.assert_any_call(version=version)
        releaser.release.assert_called_once_with(
            resource_version_name=resource_version_name,
            stage_names=stage,
        )

    def test_handle_version_changed(
        self,
        command,
        fetcher,
        releaser,
        faker,
        definition_file,
        default_command_flags,
    ):
        current_version = "1.0.1"
        definition_file.write(yaml.dump({"version": current_version}))
        latest_version = "1.0.0"
        resource_version_name = faker.pystr()
        fetcher.latest_resource_version.return_value = {
            "version": latest_version,
        }
        releaser.create_resource_version.return_value = {"name": resource_version_name}

        stage = faker.pystr()
        command.handle(stage=stage, **default_command_flags)

        releaser.create_resource_version.assert_any_call(version=current_version)
        releaser.release.assert_any_call(
            resource_version_name=resource_version_name,
            stage_names=stage,
        )

    def test_handle_version_not_set(
        self,
        command,
        fetcher,
        releaser,
        faker,
        resource_sync_manager,
        default_command_flags,
    ):
        version = "1.0.0"
        stage = faker.pystr()
        resource_version_name = faker.pystr()
        fetcher.latest_resource_version.return_value = {
            "version": version,
            "name": resource_version_name,
        }
        releaser.release.return_value = {
            "resource_version_name": resource_version_name,
            "resource_version_title": faker.pystr(),
            "stage_names": [stage],
        }

        resource_sync_manager.is_dirty.return_value = False
        command.handle(stage=stage, **default_command_flags)

        releaser.create_resource_version.assert_not_called()
        releaser.release.assert_called_once_with(
            resource_version_name=resource_version_name,
            stage_names=stage,
        )
