
import numpy as np
from matplotlib import pyplot as plt
import cv2
import random
import os
from tqdm.notebook import tqdm
from joblib import Parallel, delayed
import math
import json
from datetime import datetime
from scipy import sparse
import pyvips
import shutil

import postprocessing_workers.postprocessing_for_bitmap_worker as postprocessing_for_bitmap_worker


import multiprocessing
#print(multiprocessing.cpu_count())
PROCESSES = 8


solution_dir='Solution_1208/' # set path to metadata-preprocessing output

path_to_tif = 'input.tif'
path_to_json = 'input.json'
target_map_name = 'intput'

target_dir_img = 'LOAM_Intermediate/data/cma/imgs'
target_dir_mask = 'LOAM_Intermediate/data/cma/masks'

target_dir_img_small = 'LOAM_Intermediate/data/cma_small/imgs'
target_dir_mask_small = 'LOAM_Intermediate/data/cma_small/masks'

performance_evaluation = False




def multiprocessing_setting():
    global PROCESSES

    multiprocessing.set_start_method('spawn', True)
    if PROCESSES > multiprocessing.cpu_count():
        PROCESSES = (int)(multiprocessing.cpu_count()/2)


def dir_setting():
    os.makedirs(os.path.dirname(os.path.join(solution_dir, 'LOAM_Intermediate', 'data/')), exist_ok=True)
    os.makedirs(os.path.dirname(os.path.join(solution_dir, 'LOAM_Intermediate', 'data', 'cma/')), exist_ok=True)
    os.makedirs(os.path.dirname(os.path.join(solution_dir, 'LOAM_Intermediate', 'data', 'cma_small/')), exist_ok=True)

    global target_dir_img
    global target_dir_mask
    global target_dir_img_small
    global target_dir_mask_small

    target_dir_img = os.path.join(solution_dir, 'LOAM_Intermediate/data/cma/imgs/')
    target_dir_mask = os.path.join(solution_dir, 'LOAM_Intermediate/data/cma/masks/')
    target_dir_img_small = os.path.join(solution_dir, 'LOAM_Intermediate/data/cma_small/imgs/')
    target_dir_mask_small = os.path.join(solution_dir, 'LOAM_Intermediate/data/cma_small/masks/')

    os.makedirs(os.path.dirname(target_dir_img), exist_ok=True)
    os.makedirs(os.path.dirname(os.path.join(target_dir_img, 'sup/')), exist_ok=True)
    os.makedirs(os.path.dirname(target_dir_mask), exist_ok=True)
    os.makedirs(os.path.dirname(os.path.join(target_dir_mask, 'sup/')), exist_ok=True)
    os.makedirs(os.path.dirname(target_dir_img_small), exist_ok=True)
    os.makedirs(os.path.dirname(os.path.join(target_dir_img_small, 'sup/')), exist_ok=True)
    os.makedirs(os.path.dirname(target_dir_mask_small), exist_ok=True)
    os.makedirs(os.path.dirname(os.path.join(target_dir_mask_small, 'sup/')), exist_ok=True)

    #shutil.copyfile('targeted_map.csv', 'LOAM_Intermediate/targeted_map.csv')
    shutil.copyfile(os.path.join(solution_dir, 'LOAM_Intermediate/Metadata_Preprocessing', 'intermediate9/auxiliary_info.csv'), os.path.join(solution_dir, 'LOAM_Intermediate/data/auxiliary_info.csv'))
    print('Set up directories in "'+str(os.path.join(solution_dir, 'LOAM_Intermediate/data'))+'"')


def file_summary():
    global candidate_map_name_for_polygon
    global candidate_legend_name_for_polygon

    candidate_map_name_for_polygon = []
    candidate_legend_name_for_polygon = []


    if os.path.isfile(path_to_json) == True:
        if '.geojson' in path_to_json:
            poly_counter = 0
            poly_name_list = []

            with open(path_to_json) as f:
                gj = json.load(f)
            for this_gj in gj['features']:
                this_property = this_gj['properties']
                names = this_property['abbreviation']
                if len(names) == 0:
                    names = str(this_property['id'])+'_poly'
                else:
                    names = names+'_poly'

                poly_name_list.append(names)
                poly_counter = poly_counter + 1

            if poly_counter > 0:
                candidate_map_name_for_polygon.append(target_map_name)
                candidate_legend_name_for_polygon.append(poly_name_list)
                
        elif '.json' in path_to_json:
            print('As the format for gpkg is not determined, please provide json file in competition format to indicate the map key of a map at this stage.')
            print('Will update to read the gpkg file once the format is determined...')

            poly_counter = 0
            poly_name_list = []

            with open(path_to_json) as f:
                gj = json.load(f)
            for this_gj in gj['shapes']:
                #print(this_gj)
                names = this_gj['label']
                features = this_gj['points']
                
                if '_poly' not in names and '_pt' not in names and '_line' not in names:
                    #print(names)
                    pass
                if '_poly' not in names:
                    continue
                if names not in poly_name_list:
                    poly_name_list.append(names)
                poly_counter = poly_counter + 1

            if poly_counter > 0:
                candidate_map_name_for_polygon.append(target_map_name)
                candidate_legend_name_for_polygon.append(poly_name_list)
        else:
            print('Please provide either geojson (conforming with current schema) or json (conforming with competition schema) file...')
            print('')
            return False



def worker_postprocessing(crop_size, efficiency_trade_off):
    data_dir0 = os.path.join(solution_dir, 'LOAM_Intermediate/Metadata_Preprocessing', 'intermediate7_2/')
    data_dir1 = dir_to_groundtruth

    data_dir2 = os.path.join(solution_dir, 'LOAM_Intermediate/Metadata_Preprocessing', 'intermediate7/')
    data_dir3 = os.path.join(solution_dir, 'LOAM_Intermediate/Metadata_Preprocessing', 'intermediate5/')
    data_dir4 = os.path.join(solution_dir, 'LOAM_Intermediate/Metadata_Preprocessing', 'intermediate8_2/')


    info_set = []

    ### For polygon extraction
    for map_id in range(0, len(candidate_map_name_for_polygon)):
        runningtime_start=datetime.now()
        grid_counter = 0
        
        legend_for_multiprocessing = []
        for legend_id in range(0, len(candidate_legend_name_for_polygon[map_id])):
            target_legend = candidate_map_name_for_polygon[map_id]+'_'+candidate_legend_name_for_polygon[map_id][legend_id]+".tif" # groundtruth
            target_legend_v1 = candidate_map_name_for_polygon[map_id]+'/'+candidate_map_name_for_polygon[map_id]+'_'+candidate_legend_name_for_polygon[map_id][legend_id]+"_v7.png" # extraction
            #target_legend_v2 = candidate_map_name_for_polygon[map_id]+'/'+candidate_map_name_for_polygon[map_id]+'_'+candidate_legend_name_for_polygon[map_id][legend_id]+"_v2.png"
                        
            file_extraction = os.path.join(data_dir0, target_legend_v1)
            file_groundtruth = os.path.join(data_dir1, target_legend)
            
            if os.path.isfile(file_groundtruth) == False:
                if performance_evaluation == True:
                    print('Groundtruth is not provided... ', file_groundtruth)
                    continue
                else:
                    pass
            
            if os.path.isfile(file_extraction) == False:
                print('Extraction is not provided... ', file_extraction)
                continue

            legend_for_multiprocessing.append(legend_id)
        print(map_id, len(legend_for_multiprocessing))
        
        
        with multiprocessing.Pool(PROCESSES) as pool:
            callback = pool.starmap_async(postprocessing_for_bitmap_worker.postprocessing_for_bitmap_worker_multiple_image, [(map_id, this_legend_id, candidate_map_name_for_polygon[map_id], candidate_legend_name_for_polygon[map_id][this_legend_id], data_dir0, data_dir1, data_dir2, data_dir3, data_dir4, target_dir_img, target_dir_mask, target_dir_img_small, target_dir_mask_small, crop_size, performance_evaluation, efficiency_trade_off, ) for this_legend_id in legend_for_multiprocessing])
            multiprocessing_results = callback.get()

            for return_map_id, return_legend_id, number_of_grids in multiprocessing_results:
                grid_counter = grid_counter + number_of_grids

        runningtime_end = datetime.now()-runningtime_start

        if os.path.isfile(os.path.join(solution_dir, 'LOAM_Intermediate', 'data', 'running_time_record_v1.csv')) == False:
            with open(os.path.join(solution_dir, 'LOAM_Intermediate', 'data', 'running_time_record_v1.csv'),'w') as fd:
                fd.write('Map_Id,Map_Name,Legend_Count,RunningTime\n')
                fd.close()
        if os.path.isfile(os.path.join(solution_dir, 'LOAM_Intermediate', 'data', 'generated_grids_record_v1.csv')) == False:
            with open(os.path.join(solution_dir, 'LOAM_Intermediate', 'data', 'generated_grids_record_v1.csv'),'w') as fd:
                fd.write('Map_Id,Map_Name,Legend_Count,GeneratedGrids\n')
                fd.close()

        with open(os.path.join(solution_dir, 'LOAM_Intermediate', 'data', 'running_time_record_v1.csv'),'a') as fd:
            fd.write(str(map_id)+','+candidate_map_name_for_polygon[map_id]+','+str(len(legend_for_multiprocessing))+','+str(runningtime_end)+'\n')
            fd.close()
        with open(os.path.join(solution_dir, 'LOAM_Intermediate', 'data', 'generated_grids_record_v1.csv'),'a') as fd:
            fd.write(str(map_id)+','+candidate_map_name_for_polygon[map_id]+','+str(len(legend_for_multiprocessing))+','+str(grid_counter)+'\n')
            fd.close()

    # 59m 11.4s




def run(crop_size, efficiency_trade_off):
    multiprocessing_setting()
    dir_setting()
    file_summary()
    worker_postprocessing(crop_size, efficiency_trade_off)


def metadata_postprocessing(input_path_to_tif, input_path_to_json, input_dir_to_intermediate, input_dir_to_groundtruth, input_thread, input_efficiency_trade_off, input_performance_evaluation=False, crop_size=1024):
    global solution_dir
    global path_to_tif
    global path_to_json
    global target_map_name

    global dir_to_groundtruth
    global performance_evaluation

    global PROCESSES

    path_to_tif = input_path_to_tif
    path_to_json = input_path_to_json
    path_list = path_to_tif.replace('\\','/').split('/')
    target_map_name = os.path.splitext(path_list[-1])[0]

    solution_dir = input_dir_to_intermediate

    dir_to_groundtruth = input_dir_to_groundtruth
    performance_evaluation = input_performance_evaluation

    efficiency_trade_off = input_efficiency_trade_off

    PROCESSES = input_thread

    print('========================================== Setting of Metadata Postprocessing for Polygon Extraction ==========================================')
    print('*Intput map tif for polygon extraction => "' + path_to_tif + '"')
    print('*Intput map json for polygon extraction => "' + path_to_json + '"')

    print('*Postprocessing input directory => "' + os.path.join(solution_dir, 'LOAM_Intermediate/Metadata_Preprocessing/') + '"')
    print('*Postprocessing output directory => "' + os.path.join(solution_dir, 'LOAM_Intermediate/data/') + '"')

    print('===============================================================================================================================================')
    run(crop_size, efficiency_trade_off)







