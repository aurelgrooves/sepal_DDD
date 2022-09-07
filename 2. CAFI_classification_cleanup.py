#!/usr/bin/env python
# coding: utf-8

# # Clean up CAFI regional classification outputs from SEPAL

# This script is designed to take an output from the SEPAL classification module and clean it and amend it with additional datasets. The process is the following:
# 
# 1. import and reclass the SEPAL code output to the CAFI DDD classes described in [this table](https://docs.google.com/spreadsheets/d/1Uk_hKn0riZukzm2OQS9ZAra9xC5SaKEiEEWlKbkp8p0/edit)
# 
# 2. we remove holes in the ALOS data by integrating two classifications, one run with ALOS and one without.
# 
# 3. using the data from the Global Human Settlement [(GHS) BUILT data set](https://ghslsys.jrc.ec.europa.eu/ghs_bu2019.php) we apply built-up area
# 
# 4. assign open and closed forests according to tree cover %
# 
# 5. define montane and sub-montane forest are reclassed using the new NASA [digital elevation model](https://earthdata.nasa.gov/esds/competitive-programs/measures/nasadem)
# 
# 6. the digital elevation and ESA mangrove layer are used to remove any erroneous inland mangroves, and reclass them to swamp forest instead
# 
# 7. areas of non-permanent water defined by the JRC [Global Surface Water product](https://global-surface-water.appspot.com/) are used to correct and identify additional aquatic grasslands.
# 
# 8. national land cover data for 2015 provided by Gabon replace the regional classification area. We also include available land cover data for Annobon, Equatorial Guinea which does not have sufficient satellite data coverage. 
# 
# 9. the classification is recoded to forest/non-forest; while in the Central African Republic, areas of sparser savanna (shrub savanna) are recoded to forest to adhere to the national forest definition (>10% tree cover)
# 
# 
# the data are visualized and exported to your Google Drive or Asset. 

# In[1]:


#!pip install geemap
#pip install folium


# In[2]:


import ee
import geemap
import ee.mapclient
import folium


# In[4]:


ee.Initialize()


# Declare input data

# In[5]:


dem = ee.Image("projects/cafi_fao_congo/regional/NASAdem_congo").select('elevation')
ucl = ee.Image("projects/cafi_fao_congo/regional/congo_basin_vegetation_UCL")
optical = ee.Image("projects/cafi_fao_congo/imagery/cafi_optical_mosaic_2013_2015").select('swir1','nir','red')
fnfaxaparam = {"opacity":1,"bands":["fnf_2015"],"min":1,"max":3,"palette":["0a7e4e","c8ff95","1043ff"]}
gabon_os = ee.Image("projects/cafi_fao_congo/GAB/OS_GABON_2015").select('b1')
water = ee.ImageCollection("JRC/GSW1_3/YearlyHistory").select('waterClass')
class2015 = ee.Image("projects/cafi_fao_congo/classification/cafi_classification_alos").select('class')
class2015_no_alos = ee.Image('projects/cafi_fao_congo/classification/cafi_classification_no_alos').select('class')
aoi = ee.FeatureCollection("projects/cafi_fao_congo/regional/aoi_cafi").geometry()#.bounds(),
ALOS = ee.Image('projects/cafi_fao_congo/alos_mosaic_2015_quegan_rfdi_masked_texture')
GHSbuiltup = ee.Image("JRC/GHSL/P2016/BUILT_LDSMT_GLOBE_V1").select('built')
builtup = GHSbuiltup.remap([1,2,3,4,5,6],[0,0,1,1,1,1])
lsib = ee.FeatureCollection('projects/cafi_fao_congo/regional/congo_basin_lsib')
countries_raster =ee.Image('projects/cafi_fao_congo/regional/cafi_countries')
treecover2015 = ee.Image('projects/cafi_fao_congo/regional/treecover_2015_30m')
not_gabon = countries_raster.neq(6)
holes = not_gabon.neq(1).And(gabon_os.eq(128)).unmask()
water_area = water.mosaic().clip(aoi)
seasonal = water_area.clip(aoi).eq(2).unmask()
permanent = water_area.clip(aoi).eq(3).unmask()
annobon = ee.Image('projects/cafi_fao_congo/EQG/annobon_cafi_2014').unmask()
anno_area = annobon.gt(0).unmask()
car_cam = countries_raster.eq(2).Or(countries_raster.eq(3))
mangroves = ee.Image('projects/cafi_fao_congo/classification/cafi_mangroves_2015')
ESA_worldcover = ee.ImageCollection("ESA/WorldCover/v100")


# 1. Recode classes from SEPAL to Code DDD

# In[6]:


class_values = ([1,2,3,4,5,6,7,8,9,10,11,12,13,14,15])
reclass_values = ([1,2,3,4,7,8,9,11,12,13,14,15,16,17,18])
classDDD = class2015.remap(class_values,reclass_values).unmask()
classDDD_no_alos = class2015_no_alos.remap([1,2,3,4,5,6,7,8,9,10,11,12,13,14,15],[1,2,3,4,7,8,9,11,12,13,14,15,16,17,18]).unmask()


# 2. fix ALOS holes

# In[7]:


alosholes = classDDD.eq(0).add(1)
classDDD_fill = classDDD.where(alosholes.eq(2),classDDD_no_alos)


# 3. fix built up area

# In[8]:


built17 = ee.Image.constant(17);
built_wrong = classDDD_fill.eq(17).And(builtup.neq(1))
class2015_fix = classDDD_fill.where(builtup.eq(1),built17)
class2015_fix1 = class2015_fix.where(built_wrong.eq(1),15).clip(aoi)


# 4. apply treecover for closed and open forest

# In[9]:


claire = treecover2015.lt(60)
dense = treecover2015.gte(60)
forest_to_split = class2015_fix1.eq(2).Or(class2015_fix1.eq(4))
forestclaireseche = forest_to_split.eq(1).And(claire.eq(1))
forestdenseseche = forest_to_split.eq(1).And(dense.eq(1))

class2015_fix2 = class2015_fix1.where(forestclaireseche.eq(1),4)
class2015_fix3 = class2015_fix2.where(forestdenseseche.eq(1),2)


# 5. fix montane forest based on elevation

# In[10]:


montane = dem.gte(1750).And(class2015_fix1.eq(1))
submontane = dem.lt(1750).And(dem.gte(1100).And(class2015_fix1.eq(1)))
class2015_fix4 = class2015_fix3.where(submontane.eq(1),5)
class2015_fix5 = class2015_fix4.where(montane.eq(1),6)
gabon_mask = gabon_os.neq(128)


# 6. fix mangrove based on elevation and within a 500m buffer of ESA Mangrove 2020

# In[13]:


ESA_mang = ESA_worldcover.first().eq(95).clip(aoi)
buffer_dist = 500
mang_buffer = ESA_mang.focal_max(buffer_dist,'square','meters')
mangarea = dem.lte(35).And(class2015_fix5.lte(12)).updateMask(mang_buffer).unmask()
nomang = dem.gte(35).Or(countries_raster.eq(3)).unmask()
mangadd = mangroves.eq(1).And(mangarea.eq(1)).unmask()
mangfix = mangroves.eq(1).And(nomang.eq(1)).unmask()
class2015_fix6 = class2015_fix5.where(mangadd.eq(1),7)
class2015_fix7 = class2015_fix6.where(mangfix.eq(1),8)


# 7. fix water and prairies with JRC data

# In[14]:


prairie = seasonal.eq(1).And(class2015_fix7.neq(14).And(class2015_fix7.neq(18)))
class2015_fixwater1 = class2015_fix7.where(prairie.eq(1),14)
class2015_fixwater = class2015_fixwater1.where(permanent.eq(1),18).unmask()


# 8. add gabon and annobon data

# In[15]:


class2015_wgab = class2015_fixwater.where(not_gabon.neq(1),gabon_os)
class2015_clean = class2015_wgab.where(holes.eq(1),class2015_fixwater)
class2015_final = class2015_clean.where(anno_area.gt(0),annobon)


# 9. apply forest definitions to cameroun and central african republic

# In[16]:


caf_sav = car_cam.eq(1).And(class2015_final.eq(12))
fnf = class2015_final.remap([1,2,3,4,5,6,7,8,9,11,12,13,14,15,16,17,18],[1,1,1,1,1,1,1,1,1,1,2,2,2,2,2,2,3]).clip(aoi)
fnf_final = fnf.where(caf_sav.eq(1),1).clip(lsib)


# In[17]:


#print(class2015_final)


# ## visualize layers

# In[29]:


Map = geemap.Map()


# In[30]:


Map = geemap.Map(center=(-2, 21), zoom=5)
Map


# add classification to map

# In[31]:


classpalette = [
  'darkgreen', # 1- foret dense
  'green', # 2 - forest dense seche
  'limegreen',  # 3 - foret secondaire
   '#90ee90', # 4 - foret claire seche
  'mediumaquamarine', #5 submontane
  'darkcyan', #6 montane
  'darkmagenta', # 7 -mangrove
  'teal', #8- foret marecageuse
  'darkseagreen', # 9- foret galeries
  'saddlebrown', #10 plantations
  'DarkOliveGreen',#  11 savanne arboree
  'gold', # 12 - savanne arbustive
  'khaki',  # 13 - savanne herbacee
  'steelblue', #14 -prairie aquatique
  'grey', # 15 - sols nus
  'tan', # 16- terres cultivées
  'maroon', #17- zone baties
  'blue', #18 - eau
'#988558' #//19 nf savane arbustive
]

class_params = {
  'min': 1,
  'max': 18,
  'palette': classpalette}

Map.addLayer(class2015_final, {'min':1, 'max':19, 'palette':classpalette}, 'Classification CAFI 2015')


# add forest/non forest

# In[33]:


fnfparam = {"opacity":1,"bands":["remapped"],"palette":["0c4b13","cadea2","0a4aff"]}
fnf_map =fnf_final.select('b1')
Map.addLayer(fnf_final, fnfparam, 'Masque Forêt')


# add optical mosaic

# In[35]:


optparam = {"opacity":1,"bands":["swir1","nir","red"],"min":144,"max":3914,"gamma":1}
optical = ee.Image("projects/cafi_fao_congo/imagery/cafi_optical_mosaic_2013_2015").select('swir1','nir','red')
Map.addLayer(optical, optparam, 'optical mosaic')


# In[36]:


legend_dict = {
    '1 Forêt Dense': '006400',
    '2 Forêt Dense Seche': '1A8000',
    '3 Forêt Secondaire': '32CD32',
    '4 Forêt Claire Seche': '2E8B57',
    '5 Forêt Sub-Montagnarde': '5F9EA0',
    '6 Forêt Montagnarde': '66CDAA',
    '7 Mangrove': '8D008B',
    '8 Forêt Marécageuse': '008080',
    '9 Forêt Galéries': '8FBC8F',
    #'10 Plantations': 'saddlebrown',
    '11 Savane Arborée': '556B2F',
    '12 Savane Arbustive': 'FFD700',
    '13 Savane Herbacée': 'F0E68C',
    '14 Prairie Aquatique': '4682B4',
    '15 Sols Nus': '808080',
    '16 Terres Cultivées': 'D2B48C',
    '17 Zones Baties': '800000',
    '18 Eau': '0000FF',
    '19 Savane Arbustive - NF':'#988558'
}
Map.add_legend(legend_title="CAFI Classification", legend_dict=legend_dict)


# In[37]:


Map.addLayer(fnf_final, fnfparam, 'CAFI Foret/Non-Foret',False)


# ### Export results

# In[ ]:


classexport = ee.batch.Export.image.toDrive(image=class2015_final,  # an ee.Image object.
                                     region=aoi,  # an ee.Geometry object.
                                     description='cafi classification',
                                     folder='GEE',
                                     fileNamePrefix='LC_cafi_ddd_2015',
                                     scale=30,
                                     crs='EPSG:3857')


# In[ ]:


classexport.start()


# In[ ]:


classexport.status()


# In[ ]:


fnfexport = ee.batch.Export.image.toDrive(image=fnf_final,  # an ee.Image object.
                                     region=aoi,  # an ee.Geometry object.
                                     description='cafi_forest_mask',
                                     folder='GEE',
                                     fileNamePrefix='FNF_cafi',
                                     scale=30,
                                     crs='EPSG:3857')


# In[ ]:


fnfexport.start()


# In[ ]:


fnfexport.status()

