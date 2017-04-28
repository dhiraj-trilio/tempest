# Copyright 2014 IBM Corp.
#
#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.

from tempest.api.workloadmgr import base
from tempest import config
from tempest import test
import json
import sys
from tempest import api
from oslo_log import log as logging
from tempest.common import waiters
from tempest import tvaultconf
import time
LOG = logging.getLogger(__name__)
CONF = config.CONF


class WorkloadsTest(base.BaseWorkloadmgrTest):

    credentials = ['primary']

    @classmethod
    def setup_clients(cls):
        super(WorkloadsTest, cls).setup_clients()
        cls.client = cls.os.wlm_client

    @test.attr(type='smoke')
    @test.idempotent_id('9fe07175-912e-49a5-a629-5f52eeada4c9')
    def test_data_integrity(self):
        self.total_workloads=1
        self.vms_per_workload=2
        self.volume_size=1
        self.workload_instances = []
        self.workload_volumes = []
        self.workloads = []
        self.full_snapshots = []
        self.md5sums_dir_before = {}
        self.md5sums_dir_after = {}
        self.incr_snapshots = []
        self.restores = []
        self.fingerprint = ""
        self.vm_details_list = []
        self.original_fingerprint = ""
        self.vms_details = []

        self.original_fingerprint = self.create_key_pair(tvaultconf.key_pair_name)
        for vm in range(0,self.vms_per_workload):
             vm_id = self.create_vm()
             self.workload_instances.append(vm_id)
             volume_id1 = self.create_volume(self.volume_size,tvaultconf.volume_type)
             volume_id2 = self.create_volume(self.volume_size,tvaultconf.volume_type)
             self.workload_volumes.append(volume_id1)
             self.workload_volumes.append(volume_id2)
             self.attach_volume(volume_id1, vm_id, device="/dev/vdb")
             self.attach_volume(volume_id2, vm_id,device="/dev/vdc")

        floating_ips_list = self.get_floating_ips()

        for id in range(len(self.workload_instances)):
            self.set_floating_ip((floating_ips_list[id].encode('ascii','ignore')), self.workload_instances[id])
            self.execute_command_disk_create(floating_ips_list[id])
            self.execute_command_disk_mount(floating_ips_list[id])

        # before restore
        self.vm_details_list = []
        for id in range(len(self.workload_instances)):
            self.vm_details_list.append(self.get_restored_vm_details(self.workload_instances[id]))

        for id in range(len(self.workload_instances)):
            self.vms_details.append(str(floating_ips_list[id]) + " security_group " + str(self.vm_details_list[id]['server']['security_groups'][0]['name']))
            self.vms_details.append(str(floating_ips_list[id]) + " keys " + str(self.vm_details_list[id]['server']['key_name']))
            self.vms_details.append(str(floating_ips_list[id]) + " floating_ip " + str(self.vm_details_list[id]['server']['addresses']['int-net'][1]['addr']))
            self.vms_details.append(str(floating_ips_list[id]) + " vm_name " + str(self.vm_details_list[id]['server']['name']))
            self.vms_details.append(str(floating_ips_list[id]) + " vm_status " + str(self.vm_details_list[id]['server']['status']))
            self.vms_details.append(str(floating_ips_list[id]) + " vm_power_status " + str(self.vm_details_list[id]['server']['OS-EXT-STS:vm_state']))
            self.vms_details.append(str(floating_ips_list[id]) + " availability_zone " + str(self.vm_details_list[id]['server']['OS-EXT-AZ:availability_zone']))
            self.vms_details.append(str(floating_ips_list[id]) + " flavor " + str(self.vm_details_list[id]['server']['flavor']['id']))

        LOG.debug("vm details list before backups" + str( self.vm_details_list))
        LOG.debug("vm details dir before backups" + str( self.vms_details))

        self.md5sums_dir_before = self.data_populate_before_backup(self.workload_instances, floating_ips_list, 5)

        # create workload, take backup
        self.workload_id=self.workload_create(self.workload_instances,tvaultconf.parallel)
        self.snapshot_id=self.workload_snapshot(self.workload_id, True)
        self.wait_for_workload_tobe_available(self.workload_id)
        self.assertEqual(self.getSnapshotStatus(self.workload_id, self.snapshot_id), "available")
	self.workload_reset(self.workload_id)
        time.sleep(40)
        self.delete_vms(self.workload_instances)
        self.restore_id=self.snapshot_restore(self.workload_id, self.snapshot_id)
        self.wait_for_snapshot_tobe_available(self.workload_id, self.snapshot_id)
        self.assertEqual(self.getRestoreStatus(self.workload_id, self.snapshot_id, self.restore_id), "available","Workload_id: "+self.workload_id+" Snapshot_id: "+self.snapshot_id+" Restore id: "+self.restore_id)

        # after restore
        # verification
        # get restored vms list
        self.vm_list = []
        self.restored_vm_details_list = []
        self.vm_list  =  self.get_restored_vm_list(self.restore_id)
        LOG.debug("Restored vms : " + str (self.vm_list))
        floating_ips_list_after_restore = []
        for id in range(len(self.vm_list)):
            self.restored_vm_details_list.append(self.get_restored_vm_details(self.vm_list[id]))

        for id in range(len(self.restored_vm_details_list)):
            floating_ips_list_after_restore.append(self.restored_vm_details_list[id]['server']['addresses']['int-net'][1]['addr'])
            LOG.debug("floating_ips_list_after_restore: " + str(floating_ips_list_after_restore))

        self.vms_details_after_one_click_restore = []
        for id in range(len(self.vm_list)):
            self.vms_details_after_one_click_restore.append(str(floating_ips_list_after_restore[id]) + " security_group " + str(self.restored_vm_details_list[id]['server']['security_groups'][0]['name']))
            self.vms_details_after_one_click_restore.append(str(floating_ips_list_after_restore[id]) + " keys " + str(self.restored_vm_details_list[id]['server']['key_name']))
            self.vms_details_after_one_click_restore.append(str(floating_ips_list_after_restore[id]) + " floating_ip " + str(self.restored_vm_details_list[id]['server']['addresses']['int-net'][1]['addr']))
            self.vms_details_after_one_click_restore.append(str(floating_ips_list_after_restore[id]) + " vm_name " + str(self.restored_vm_details_list[id]['server']['name']))
            self.vms_details_after_one_click_restore.append(str(floating_ips_list_after_restore[id]) + " vm_status " + str(self.restored_vm_details_list[id]['server']['status']))
            self.vms_details_after_one_click_restore.append(str(floating_ips_list_after_restore[id]) + " vm_power_status " + str(self.restored_vm_details_list[id]['server']['OS-EXT-STS:vm_state']))
            self.vms_details_after_one_click_restore.append(str(floating_ips_list_after_restore[id]) + " availability_zone " + str(self.restored_vm_details_list[id]['server']['OS-EXT-AZ:availability_zone']))
            self.vms_details_after_one_click_restore.append(str(floating_ips_list_after_restore[id]) + " flavor " + str(self.restored_vm_details_list[id]['server']['flavor']['id']))


        LOG.debug("vm details list after restore" + str( self.restored_vm_details_list))
        LOG.debug("vm details dir after restore" + str( self.vms_details_after_one_click_restore))


        self.assertTrue(self.vms_details==self.vms_details_after_one_click_restore, "virtual instances details does not match")


        self.md5sums_dir_after = self.calculate_md5_after_restore(self.vm_list, floating_ips_list_after_restore)
    #
    #     # verification one-click restore
        for id in range(len(self.vm_list)):
            self.assertTrue(self.md5sums_dir_before[str(floating_ips_list_after_restore[id])]==self.md5sums_dir_after[str(floating_ips_list_after_restore[id])], "md5sum verification unsuccessful for ip" + str(floating_ips_list_after_restore[id]))
    #
    #     # incremental change
        self.md5sums_dir_before = self.data_populate_before_backup(self.vm_list, floating_ips_list_after_restore, 7)
    #
    #     # incremental snapshot backup
        self.snapshot_id=self.workload_snapshot(self.workload_id, False)
        self.wait_for_workload_tobe_available(self.workload_id)
        self.assertEqual(self.getSnapshotStatus(self.workload_id, self.snapshot_id), "available")
	self.workload_reset(self.workload_id)
        time.sleep(40)

        # no vm deletion for selective restore

        # diassociate floating ips#  deassociate floating ips from previous vms
        for id in range(len(self.vm_list)):
            self.diassociate_floating_ip(floating_ips_list_after_restore[id], self.vm_list[id])


        self.restore_id=self.snapshot_selective_restore(self.workload_id, self.snapshot_id)
        self.wait_for_snapshot_tobe_available(self.workload_id, self.snapshot_id)
        self.assertEqual(self.getRestoreStatus(self.workload_id, self.snapshot_id, self.restore_id), "available","Workload_id: "+self.workload_id+" Snapshot_id: "+self.snapshot_id+" Restore id: "+self.restore_id)



        # after selective restore_id and incremental change
        # after restore
        self.vm_list = []
        # restored_vm_details = ""
        self.restored_vm_details_list = []
        self.vm_list  =  self.get_restored_vm_list(self.restore_id)
        LOG.debug("Restored vms : " + str (self.vm_list))
        floating_ips_list_after_restore = []
        for id in range(len(self.vm_list)):
            self.restored_vm_details_list.append(self.get_restored_vm_details(self.vm_list[id]))
        LOG.debug("Restored vm detaild list after incremental change " + str(self.restored_vm_details_list))

        for id in range(len(self.restored_vm_details_list)):
            floating_ips_list_after_restore.append(self.restored_vm_details_list[id]['server']['addresses']['int-net'][1]['addr'])

        self.vms_details_after_selective_restore = []
        for id in range(len(self.vm_list)):
            self.vms_details_after_selective_restore.append(str(floating_ips_list_after_restore[id]) + " security_group " + str(self.restored_vm_details_list[id]['server']['security_groups'][0]['name']))
            self.vms_details_after_selective_restore.append(str(floating_ips_list_after_restore[id]) + " keys " + str(self.restored_vm_details_list[id]['server']['key_name']))
            self.vms_details_after_selective_restore.append(str(floating_ips_list_after_restore[id]) + " floating_ip " + str(self.restored_vm_details_list[id]['server']['addresses']['int-net'][1]['addr']))
            self.vms_details_after_selective_restore.append(str(floating_ips_list_after_restore[id]) + " vm_name " + str(self.restored_vm_details_list[id]['server']['name']))
            self.vms_details_after_selective_restore.append(str(floating_ips_list_after_restore[id]) + " vm_status " + str(self.restored_vm_details_list[id]['server']['status']))
            self.vms_details_after_selective_restore.append(str(floating_ips_list_after_restore[id]) + " vm_power_status " + str(self.restored_vm_details_list[id]['server']['OS-EXT-STS:vm_state']))
            self.vms_details_after_selective_restore.append(str(floating_ips_list_after_restore[id]) + " availability_zone " + str(self.restored_vm_details_list[id]['server']['OS-EXT-AZ:availability_zone']))
            self.vms_details_after_selective_restore.append(str(floating_ips_list_after_restore[id]) + " flavor " + str(self.restored_vm_details_list[id]['server']['flavor']['id']))

        self.md5sums_dir_after = self.calculate_md5_after_restore(self.vm_list, floating_ips_list_after_restore)
        self.assertTrue(self.vms_details==self.vms_details_after_one_click_restore, "virtual instances details does not match")

        # verification selective restore incremental change
        for id in range(len(self.vm_list)):
            self.assertTrue(self.md5sums_dir_before[str(floating_ips_list_after_restore[id])]==self.md5sums_dir_after[str(floating_ips_list_after_restore[id])], "md5sum verification unsuccessful for ip" + str(floating_ips_list_after_restore[id]))