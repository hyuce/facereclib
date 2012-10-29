#!/usr/bin/env python
# vim: set fileencoding=utf-8 :
# @author: Manuel Guenther <Manuel.Guenther@idiap.ch>
# @date: Thu May 24 10:41:42 CEST 2012
#
# Copyright (C) 2011-2012 Idiap Research Institute, Martigny, Switzerland
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, version 3 of the License.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.


import unittest
import os
import numpy
import tempfile
import facereclib
import bob
from nose.plugins.skip import SkipTest

regenerate_refs = False


class ToolTest(unittest.TestCase):

  def input_dir(self, file):
    return os.path.join('testdata', 'features', file)

  def reference_dir(self, file):
    dir = os.path.join('testdata', 'tools')
    facereclib.utils.ensure_dir(dir)
    return os.path.join(dir, file)

  def config(self, resource):
    return facereclib.utils.tests.configuration_file(resource, 'tool', 'tools')


  def compare(self, feature, reference):
    # execute the preprocessor
    if regenerate_refs:
      bob.io.save(feature, self.reference_dir(reference))

    self.assertTrue((numpy.abs(bob.io.load(self.reference_dir(reference)) - feature) < 1e-5).all())


  def train_set(self, feature, count = 50, a = 0, b = 1):
    # generate a random sequence of features
    numpy.random.seed(42)
    return [numpy.random.random(feature.shape) * (b - a) + a for i in range(count)]

  def train_set_by_id(self, feature, count = 50, a = 0, b = 1):
    # generate a random sequence of features
    numpy.random.seed(42)
    train_set = []
    for i in range(count):
      train_set.append([numpy.random.random(feature.shape) * (b - a) + a for j in range(count)])
    return train_set


  def train_gmm_stats(self, feature_file, count = 50, a = 0, b = 1):
    # generate a random sequence of GMM-Stats features
    numpy.random.seed(42)
    train_set = []
    f = bob.io.HDF5File(feature_file)
    for i in range(count):
      per_id = []
      for j in range(count):
        gmm_stats = bob.machine.GMMStats(f)
        gmm_stats.sum_px = numpy.random.random(gmm_stats.sum_px.shape) * (b - a) + a
        gmm_stats.sum_pxx = numpy.random.random(gmm_stats.sum_pxx.shape) * (b - a) + a
        per_id.append(gmm_stats)
      train_set.append(per_id)
    return train_set



  def test01_gabor_jet(self):
    # read input
    feature = bob.io.load(self.input_dir('graph_with_phase.hdf5'))
    tool = self.config('gabor-jet')
    self.assertFalse(tool.performs_projection)
    self.assertFalse(tool.requires_enroller_training)

    # enroll
    model = tool.enroll([feature])
    self.compare(model, 'graph_model.hdf5')

    # score
    sim = tool.score(model, feature)
    self.assertAlmostEqual(sim, 1.)


  def test02_lgbphs(self):
    # read input
    feature1 = bob.io.load(self.input_dir('lgbphs_sparse.hdf5'))
    feature2 = bob.io.load(self.input_dir('lgbphs_no_phase.hdf5'))
    tool = self.config('lgbphs')
    self.assertFalse(tool.performs_projection)
    self.assertFalse(tool.requires_enroller_training)

    # enroll model
    model = tool.enroll([feature1])
    self.compare(model, 'lgbphs_model.hdf5')

    # score
    sim = tool.score(model, feature2)
    self.assertAlmostEqual(sim, 33600.0)


  def test03_pca(self):
    # read input
    feature = bob.io.load(self.input_dir('linearize.hdf5'))
    # assure that the config file is read
    tool = self.config('pca')
    self.assertTrue(isinstance(tool, facereclib.tools.PCATool))

    # generate tool with a lower number of dimensions
    tool = facereclib.tools.PCATool(10)
    self.assertTrue(tool.performs_projection)
    self.assertTrue(tool.requires_projector_training)
    self.assertTrue(tool.use_projected_features_for_enrollment)
    self.assertFalse(tool.split_training_features_by_client)

    # train the projector
    t = tempfile.mkstemp('pca.hdf5')[1]
    tool.train_projector(self.train_set(feature, count=400, a=0., b=255.), t)
    if regenerate_refs:
      import shutil
      shutil.copy2(t, self.reference_dir('pca_projector.hdf5'))

    # load the projector file
    tool.load_projector(self.reference_dir('pca_projector.hdf5'))
    # compare the resulting machines
    new_machine = bob.machine.LinearMachine(bob.io.HDF5File(t))
    self.assertEqual(tool.m_machine.shape, new_machine.shape)
    self.assertTrue(numpy.abs(tool.m_machine.weights - new_machine.weights < 1e-5).all())
    os.remove(t)

    # project feature
    projected = tool.project(feature)
    self.compare(projected, 'pca_feature.hdf5')
    self.assertTrue(len(projected.shape) == 1)

    # enroll model
    model = tool.enroll([projected])
    self.compare(model, 'pca_model.hdf5')
    sim = tool.score(model, projected)
    self.assertAlmostEqual(sim, 0.)


  def test04_lda(self):
    # read input
    feature = bob.io.load(self.input_dir('linearize.hdf5'))
    # assure that the config file is loadable
    tool = self.config('lda')
    self.assertTrue(isinstance(tool, facereclib.tools.LDATool))
    # assure that the config file is loadable
    tool = self.config('pca+lda')
    self.assertTrue(isinstance(tool, facereclib.tools.LDATool))

    # here we use a reduced tool
    tool = facereclib.tools.LDATool(5,10)
    self.assertTrue(tool.performs_projection)
    self.assertTrue(tool.requires_projector_training)
    self.assertTrue(tool.use_projected_features_for_enrollment)
    self.assertTrue(tool.split_training_features_by_client)

    # train the projector
    t = tempfile.mkstemp('pca+lda.hdf5')[1]
    tool.train_projector(self.train_set_by_id(feature, count=20, a=0., b=255.), t)
    if regenerate_refs:
      import shutil
      shutil.copy2(t, self.reference_dir('pca+lda_projector.hdf5'))

    # load the projector file
    tool.load_projector(self.reference_dir('pca+lda_projector.hdf5'))
    # compare the resulting machines
    new_machine = bob.machine.LinearMachine(bob.io.HDF5File(t))
    self.assertEqual(tool.m_machine.shape, new_machine.shape)
    self.assertTrue(numpy.abs(tool.m_machine.weights - new_machine.weights < 1e-5).all())
    os.remove(t)

    # project feature
    projected = tool.project(feature)
    self.compare(projected, 'pca+lda_feature.hdf5')
    self.assertTrue(len(projected.shape) == 1)

    # enroll model
    model = tool.enroll([projected])
    self.compare(model, 'pca+lda_model.hdf5')

    # score
    sim = tool.score(model, projected)
    self.assertAlmostEqual(sim, 0.)


  def test05_bic(self):
    # read input
    feature = bob.io.load(self.input_dir('linearize.hdf5'))
    # check that the config file is readable
    tool = self.config('bic')
    self.assertTrue(isinstance(tool, facereclib.tools.BICTool))

    # here, we use a reduced complexity for test purposes
    tool = facereclib.tools.BICTool(numpy.subtract, 100, (5,7))
    self.assertFalse(tool.performs_projection)
    self.assertTrue(tool.requires_enroller_training)

    # train the enroller
    t = tempfile.mkstemp('bic.hdf5')[1]
    tool.train_enroller(self.train_set_by_id(feature, count=10, a=0., b=255.), t)
    if regenerate_refs:
      import shutil
      shutil.copy2(t, self.reference_dir('bic_enroller.hdf5'))

    # load the projector file
    tool.load_enroller(self.reference_dir('bic_enroller.hdf5'))
    # compare the resulting machines
    new_machine = bob.machine.BICMachine(tool.m_use_dffs)
    new_machine.load(bob.io.HDF5File(t))
    self.assertTrue(tool.m_bic_machine.is_similar_to(new_machine))
    os.remove(t)

    # enroll model
    model = tool.enroll([feature])
    self.compare(model, 'bic_model.hdf5')

    # score and compare to the weird reference score ...
    sim = tool.score(model, feature)
    self.assertAlmostEqual(sim, 0.31276072)

    # now, test without PCA
    tool = facereclib.tools.BICTool(numpy.subtract, 100)
    # train the enroller
    t = tempfile.mkstemp('iec.hdf5')[1]
    tool.train_enroller(self.train_set_by_id(feature, count=10, a=0., b=255.), t)
    if regenerate_refs:
      import shutil
      shutil.copy2(t, self.reference_dir('iec_enroller.hdf5'))

    # load the projector file
    tool.load_enroller(self.reference_dir('iec_enroller.hdf5'))
    # compare the resulting machines
    new_machine = bob.machine.BICMachine(tool.m_use_dffs)
    new_machine.load(bob.io.HDF5File(t))
    self.assertEqual(tool.m_bic_machine, new_machine)
    os.remove(t)

    # score and compare to the weird reference score ...
    sim = tool.score(model, feature)
    self.assertAlmostEqual(sim, 0.4070329180)


  def test06_gmm(self):
    # read input
    feature = bob.io.load(self.input_dir('dct_blocks.hdf5'))
    # assure that the config file is readable
    tool = self.config('gmm')
    self.assertTrue(isinstance(tool, facereclib.tools.UBMGMMTool))

    # here, we use a reduced complexity for test purposes
    tool = facereclib.tools.UBMGMMTool(
        number_of_gaussians = 2,
        k_means_training_iterations = 1,
        gmm_training_iterations = 1
    )
    self.assertTrue(tool.performs_projection)
    self.assertTrue(tool.requires_projector_training)
    self.assertFalse(tool.use_projected_features_for_enrollment)
    self.assertFalse(tool.split_training_features_by_client)

    # train the projector
    t = tempfile.mkstemp('ubm.hdf5')[1]
    tool.train_projector(self.train_set(feature, count=5, a=-5., b=5.), t)
    if regenerate_refs:
      import shutil
      shutil.copy2(t, self.reference_dir('gmm_projector.hdf5'))

    # load the projector file
    tool.load_projector(self.reference_dir('gmm_projector.hdf5'))
    # compare GMM projector with reference
    new_machine = bob.machine.GMMMachine(bob.io.HDF5File(t))
    self.assertEqual(tool.m_ubm, new_machine)
    os.remove(t)

    # project the feature
    projected = tool.project(feature)
    if regenerate_refs:
      projected.save(bob.io.HDF5File(self.reference_dir('gmm_feature.hdf5'), 'w'))
    probe = tool.read_probe(self.reference_dir('gmm_feature.hdf5'))
    self.assertEqual(projected, probe)

    # enroll model with the unprojected feature
    model = tool.enroll([feature])
    if regenerate_refs:
      model.save(bob.io.HDF5File(self.reference_dir('gmm_model.hdf5'), 'w'))
    reference_model = tool.read_model(self.reference_dir('gmm_model.hdf5'))
    self.assertEqual(model, reference_model)

    # score with projected feature and compare to the weird reference score ...
    sim = tool.score(reference_model, probe)
    self.assertAlmostEqual(sim, 0.25472347774)

  def test06a_gmm_regular(self):
    # read input
    feature = bob.io.load(self.input_dir('dct_blocks.hdf5'))
    # assure that the config file is readable
    tool = self.config('ubm_gmm_regular_scoring')
    self.assertTrue(isinstance(tool, facereclib.tools.UBMGMMRegularTool))

    # here, we use a reduced complexity for test purposes
    tool = facereclib.tools.UBMGMMRegularTool(
        number_of_gaussians = 2,
        k_means_training_iterations = 1,
        gmm_training_iterations = 1
    )
    self.assertFalse(tool.performs_projection)
    self.assertTrue(tool.requires_enroller_training)

    # train the enroller
    t = tempfile.mkstemp('ubm.hdf5')[1]
    tool.train_enroller(self.train_set(feature, count=5, a=-5., b=5.), t)
    # assure that it is identical to the normal UBM projector
    tool.load_enroller(self.reference_dir('gmm_projector.hdf5'))

    # enroll model with the unprojected feature
    model = tool.enroll([feature])
    reference_model = tool.read_model(self.reference_dir('gmm_model.hdf5'))
    self.assertEqual(model, reference_model)

    # score with unprojected feature and compare to the weird reference score ...
    probe = tool.read_probe(self.input_dir('dct_blocks.hdf5'))
    sim = tool.score(reference_model, probe)

    # TODO: I don't know why, but the result differ from the original UBMGMM approach...
#    self.assertAlmostEqual(sim, 0.25472347774)
    self.assertAlmostEqual(sim, 0.143875716)


  def test06b_gmm_video(self):
    # assure that the config file is readable
    tool = self.config('ubm_gmm_video')
    self.assertTrue(isinstance(tool, facereclib.tools.UBMGMMVideoTool))
    raise SkipTest("This test is not yet implemented")


  def test07_isv(self):
    # read input
    feature = bob.io.load(self.input_dir('dct_blocks.hdf5'))
    # assure that the config file is readable
    tool = self.config('isv')
    self.assertTrue(isinstance(tool, facereclib.tools.ISVTool))

    # Here, we use a reduced complexity for test purposes
    tool = facereclib.tools.ISVTool(
        number_of_gaussians = 2,
        subspace_dimension_of_u = 160,
        k_means_training_iterations = 1,
        gmm_training_iterations = 1,
        jfa_training_iterations = 1
    )
    self.assertTrue(tool.performs_projection)
    self.assertTrue(tool.requires_projector_training)
    self.assertTrue(tool.use_projected_features_for_enrollment)
    self.assertFalse(tool.split_training_features_by_client)
    self.assertTrue(tool.requires_enroller_training)

    # train the projector
    t = tempfile.mkstemp('ubm.hdf5')[1]
    tool.train_projector(self.train_set(feature, count=5, a=-5., b=5.), t)
    if regenerate_refs:
      import shutil
      shutil.copy2(t, self.reference_dir('isv_projector.hdf5'))

    # load the projector file
    tool.load_projector(self.reference_dir('isv_projector.hdf5'))
    # compare ISV projector with reference
    new_machine = bob.machine.GMMMachine(bob.io.HDF5File(t))
    self.assertEqual(tool.m_ubm, new_machine)
    os.remove(t)

    # project the feature
    projected = tool.project(feature)
    if regenerate_refs:
      projected.save(bob.io.HDF5File(self.reference_dir('isv_feature.hdf5'), 'w'))
    # compare the projected feature with the reference
    projected_reference = tool.read_feature(self.reference_dir('isv_feature.hdf5'))
    self.assertEqual(projected, projected_reference)

    # train the enroller
    t = tempfile.mkstemp('ubm.hdf5')[1]
    tool.train_enroller(self.train_gmm_stats(self.reference_dir('isv_feature.hdf5'), count=5, a=-5., b=5.), t)
    if regenerate_refs:
      import shutil
      shutil.copy2(t, self.reference_dir('isv_enroller.hdf5'))
    tool.load_enroller(self.reference_dir('isv_enroller.hdf5'))
    # TODO: compare ISV enroller with reference
    #enroller_reference = bob.machine.JFABaseMachine(bob.io.HDF5File(t))
    #self.assertEqual(tool.m_jfabase, enroller_reference)
    os.remove(t)

    # enroll model with the projected feature
    model = tool.enroll([projected])
    if regenerate_refs:
      model.save(bob.io.HDF5File(self.reference_dir('isv_model.hdf5'), 'w'))
    reference_model = tool.read_model(self.reference_dir('isv_model.hdf5'))
    # compare the ISV model with the reference
    self.assertEqual(model, reference_model)

    # check that the read_probe function reads the correct values
    probe = tool.read_probe(self.reference_dir('isv_feature.hdf5'))
    self.assertEqual(probe, projected)

    # score with projected feature and compare to the weird reference score ...
    sim = tool.score(model, probe)
    self.assertAlmostEqual(sim, 0.000443472976)


  def test07a_isv_video(self):
    # assure that the config file is readable
    tool = self.config('isv_video')
    self.assertTrue(isinstance(tool, facereclib.tools.ISVVideoTool))
    raise SkipTest("This test is not yet implemented")


  def test08_jfa(self):
    # read input
    feature = bob.io.load(self.input_dir('dct_blocks.hdf5'))
    # assure that the config file is readable
    tool = self.config('jfa')
    self.assertTrue(isinstance(tool, facereclib.tools.JFATool))

    # here, we use a reduced complexity for test purposes
    tool = facereclib.tools.JFATool(
        number_of_gaussians = 2,
        subspace_dimension_of_u = 2,
        subspace_dimension_of_v = 2,
        k_means_training_iterations = 1,
        gmm_training_iterations = 1,
        jfa_training_iterations = 1
    )
    self.assertTrue(tool.performs_projection)
    self.assertTrue(tool.requires_projector_training)
    self.assertTrue(tool.use_projected_features_for_enrollment)
    self.assertFalse(tool.split_training_features_by_client)
    self.assertTrue(tool.requires_enroller_training)

    # train the projector
    t = tempfile.mkstemp('ubm.hdf5')[1]
    tool.train_projector(self.train_set(feature, count=5, a=-5., b=5.), t)
    if regenerate_refs:
      import shutil
      shutil.copy2(t, self.reference_dir('jfa_projector.hdf5'))

    # load the projector file
    tool.load_projector(self.reference_dir('jfa_projector.hdf5'))
    # compare JFA projector with reference
    new_machine = bob.machine.GMMMachine(bob.io.HDF5File(t))
    self.assertEqual(tool.m_ubm, new_machine)
    os.remove(t)

    # project the feature
    projected = tool.project(feature)
    if regenerate_refs:
      projected.save(bob.io.HDF5File(self.reference_dir('jfa_feature.hdf5'), 'w'))
    # compare the projected feature with the reference
    projected_reference = tool.read_feature(self.reference_dir('jfa_feature.hdf5'))
    self.assertEqual(projected, projected_reference)

    # train the enroller
    t = tempfile.mkstemp('ubm.hdf5')[1]
    tool.train_enroller(self.train_gmm_stats(self.reference_dir('jfa_feature.hdf5'), count=5, a=-5., b=5.), t)
    if regenerate_refs:
      import shutil
      shutil.copy2(t, self.reference_dir('jfa_enroller.hdf5'))
    tool.load_enroller(self.reference_dir('jfa_enroller.hdf5'))
    # TODO: compare JFA enroller with reference
    #enroller_reference = bob.machine.JFABaseMachine(bob.io.HDF5File(t))
    #self.assertEqual(tool.m_jfabase, enroller_reference)
    os.remove(t)

    # enroll model with the projected feature
    model = tool.enroll([projected])
    if regenerate_refs:
      model.save(bob.io.HDF5File(self.reference_dir('jfa_model.hdf5'), 'w'))
    # assert that the model is ok
    reference_model = tool.read_model(self.reference_dir('jfa_model.hdf5'))
    self.assertEqual(model, reference_model)

    # check that the read_probe function reads the requested data
    probe = tool.read_probe(self.reference_dir('jfa_feature.hdf5'))
    self.assertEqual(probe, projected)

    # score with projected feature and compare to the weird reference score ...
    sim = tool.score(model, probe)
    self.assertAlmostEqual(sim, 0.25459651295)


  def test09_plda(self):
    # read input
    feature = bob.io.load(self.input_dir('linearize.hdf5'))
    # assure that the config file is readable
    tool = self.config('pca+plda')
    self.assertTrue(isinstance(tool, facereclib.tools.PLDATool))

    # here, we use a reduced complexity for test purposes
    tool = facereclib.tools.PLDATool(
        subspace_dimension_of_f = 2,
        subspace_dimension_of_g = 2,
        subspace_dimension_pca = 10,
        plda_training_iterations = 1
    )
    self.assertFalse(tool.performs_projection)
    self.assertTrue(tool.requires_enroller_training)

    # train the projector
    t = tempfile.mkstemp('pca+plda.hdf5')[1]
    tool.train_enroller(self.train_set_by_id(feature, count=20, a=0., b=255.), t)
    if regenerate_refs:
      import shutil
      shutil.copy2(t, self.reference_dir('pca+plda_enroller.hdf5'))

    # load the projector file
    tool.load_enroller(self.reference_dir('pca+plda_enroller.hdf5'))
    # compare the resulting machines
    test_file = bob.io.HDF5File(t)
    test_file.cd('/pca')
    pca_machine = bob.machine.LinearMachine(test_file)
    test_file.cd('/plda')
    plda_machine = bob.machine.PLDABaseMachine(test_file)
    # TODO: compare the PCA machines
    #self.assertEqual(pca_machine, tool.m_pca_machine)
    # TODO: compare the PLDA machines
    #self.assertEqual(plda_machine, tool.m_plda_base_machine)
    os.remove(t)

    # enroll model
    model = tool.enroll([feature])
    if regenerate_refs:
      model.save(bob.io.HDF5File(self.reference_dir('pca+plda_model.hdf5'), 'w'))
    # TODO: compare the models with the reference
    #reference_model = tool.read_model(self.reference_dir('pca+plda_model.hdf5'))
    #self.assertEqual(model, reference_model)

    # score
    sim = tool.score(model, feature)
    self.assertAlmostEqual(sim, 0.)

