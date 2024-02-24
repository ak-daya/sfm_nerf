import numpy as np
import cv2
import matplotlib.pyplot as plt 
import copy
import os
import scipy.optimize as optimize
import math
from os.path import dirname, abspath
from skimage.io import imread, imshow
from skimage import transform
from EssentialMatrixFromFundamentalMatrix import EssentialMatrixFromFundamentalMatrix
from ExtractCameraPose import ExtractCameraPose
from EstimateFundamentalMatrix import *
from GetInlierRANSAC import *
from DisambiguateCameraPose import *
from rotationmatrix import *
from Visualization import *
from DataLoader import *   
from LinearTriangulation import *   
from NonlinearTriangulation import *
from PnPRANSAC import *
from NonlinearPnP import *

def main():
    # Read in images, correspondences, intrinsic matrix
    basePath = (dirname(abspath(__file__)))
    image_path = basePath + f"\\Data\\sfmdata"
    txtdata_path = basePath + f"\\Data\\sfmtxtdata"
    
    images = LoadImagesFromFolder(image_path)
    K = np.array([[531.122155322710, 0.0, 407.192550839899], [0.0, 531.541737503901, 313.308715048366], [0.0, 0.0, 1.0]])
    MatchPairs_text = LoadTextFromFolder(txtdata_path)
    Matchpairs = []
    Colorpairs = []
    MatchIndex = []
    for index, file in enumerate(MatchPairs_text):
        ImgPairs, colorpairs= Matching_pairs(file, index+1)
        Matchpairs.append(ImgPairs)
        Colorpairs.append(colorpairs)
    
    # print(returnpairs(Matchpairs, [3,1]))
    # FundamentalMatrix = np.array([[0.1, 0.2, -0.3], [0.4, 0.5, -0.6], [0.7, 0.8, -0.9]])
    # essentialMatrix = EssentialMatrix(intrinsic_matrix, FundamentalMatrix)
    # print(essentialMatrix)
    # pose = CameraPoseEstimation(essentialMatrix)
    # print(pose)
        
    # Outlier rejection for all pairs
    
    
    # First two images
    coord_pair = np.array(returnpairs(Matchpairs, [1,2]))
    coordpairs1 = coord_pair[:,0,:] #[pair[0] for pair in coord_pair]
    coordpairs2 = coord_pair[:,1,:] #[pair[0] for pair in coord_pair]
    
    # Debug
    # print(f"Number of matches: {len(coordpairs1)}")
    
    # best_points1H, best_points2H = HomographyRansac(coord_pair)
    # drawmatches(images[i], images[j], coordpairs1, coordpairs2)
    # drawmatches(images[i], images[j], best_points1H, best_points2H)

    best_points1, best_points2, inlier_index = OutlierRejectionRANSAC(coordpairs1, coordpairs2, break_percentage=0.9)
    # best_points1, best_points2 = OutlierRejectionRANSAC(np.array(best_points1H), np.array(best_points2H))

    # Debug
    print(f"Number of pruned matches: {len(best_points1)}")

    # Visualize sample of best matches
    # rand_idx = random.sample(range(best_points1.shape[0]), 16)
    # coordpairs1_sample = best_points1[rand_idx]
    # coordpairs2_sample = best_points2[rand_idx]
    # drawmatches(images[i], images[j], coordpairs1_sample, coordpairs2_sample)
    
    # Estimate fundamental matrix over best matches
    fundamentalMatrix = EstimateFundamentalMatrix(best_points1, best_points2, normalize=False)
    # print(f"F: \n{fundamentalMatrix}")
    
    # Estimate essential matrix            
    essentialMatrix = EssentialMatrixFromFundamentalMatrix(K, fundamentalMatrix)
    # print(f"F: \n{essentialMatrix}")

    # Testing for epipolar constraint
    # best_points1_hom = Homogenize(best_points1)
    # best_points2_hom = Homogenize(best_points2)
    # epiConstraint1 = 0
    # epiConstraint2 = 0
    # for i in range(best_points1_hom.shape[0]):
    #     epiConstraint1 += best_points2_hom[i] @ Fundamental_matrix @ best_points1_hom[i]
    #     epiConstraint2 += best_points2_hom[i] @ FundamentalMatrixCV2 @ best_points1_hom[i]
    # avgEpiConstraint1 = epiConstraint1/best_points1_hom.shape[0]
    # avgEpiConstraint2 = epiConstraint2/best_points1_hom.shape[0]
    # print(f"Avg Epipolar Constraint Ours: {avgEpiConstraint1}")
    # print(f"Avg Epipolar Constraint CV2: {avgEpiConstraint2}")
    
    # Estimate camera poses
    C_s, R_s = ExtractCameraPose(essentialMatrix)
    
    # Linear Triangulation
    # Iterate over poses, estimate depth and do cheirality check
    C_O = np.zeros((3,1))
    R_O = np.identity(3)

    linearDepthPts = []
    for i in range(len(R_s)):
        points = LinearTriangulation(K, C_O, R_O, C_s[i], R_s[i], best_points1, best_points2)
        linearDepthPts.append(points)
    
    # Visualize all poses
    Plot3DPointSets(linearDepthPts, ['brown','blue','pink','purple'], ['Pose 1', 'Pose 2', 'Pose 3', 'Pose 4'], 
                    [-30, 30], [-30, 30], 'Triangulation over All Possible Poses')

    # Check cheirality condition
    C, R, linearDepth = DisambiguateCameraPose(C_s, R_s, linearDepthPts)

    print(f"C: \n{C}")
    print(f"R: \n{R}")

    # Non-linear Triangulation
    X0 = linearDepth
    
    linearDepthPts = LinearTriangulation(K, C_O, R_O, C, R, best_points1, best_points2)
    P = GetProjectionMatrix(C, R, K)
    U_pred = World2Image(X0, P)
    ErrorPreOpt = ReprojectionError(U_pred, best_points2)
    
    print(f"Error Pre-Optimization: {ErrorPreOpt.mean()}")
    
    

    nonlinearDepthPts = NonLinearTriangulation(X0, K, C_O, R_O, C, R, best_points1, best_points2)
    
    U_predOpt = World2Image(nonlinearDepthPts, P)
    ErrorPostOpt = ReprojectionError(U_predOpt, best_points2)
    print(f"Error Post-Optimization: {ErrorPostOpt.mean()}")

    # Visualize Linear and Non-Linear Triangulation
    Plot3DPointSets([X0, nonlinearDepthPts], ['blue','red'], ['Linear', 'Non-Linear'], 
                    [-20, 20], [-5, 30], 'Linear and Non-Linear Triangulation')

    # print((X0 - nonlinearDepthPts)[:5])
    # print(np.linalg.norm(X0 - nonlinearDepthPts))
    
    
    # Visualizer4R(depthpoints)
    # visualizer(depthpointsCheralityCheck[max_index])

    #non-linear triangulation
    # pointsNonLinear = TriangulateDepth_NonLinear([intrinsic_matrix, C1, R1, C_s[max_index], R_s[max_index]], best_points1, best_points2, pointsLinear)
    # visualizer(pointsNonLinear)

    # best_pts3d = depthpointsCheralityCheck[max_index]
    TotalDepthPoints = []
    TotalDepthPoints.append(nonlinearDepthPts)
    Poses = [[] for _ in range(2)]   #poses = [[R_set][C_set]]
    best_points = []    
    best_points.append(best_points1)
    best_points.append(best_points2) 
    
    for i in range(3, 6):
        coord_pair = np.array(returnpairs(Matchpairs,[1,i]))
        coordpairs1 = coord_pair[:,0,:] #[pair[0] for pair in coord_pair]
        coordpairs2 = coord_pair[:,1,:] #[pair[0] for pair in coord_pair]
        best_points1, best_points2, inlier_index = OutlierRejectionRANSAC(coordpairs1, coordpairs2, break_percentage=0.9)
        print(f"Number of pruned matches: {len(best_points1)}")

        fundamentalMatrix = EstimateFundamentalMatrix(best_points1, best_points2, normalize=False)
         
        essentialMatrix = EssentialMatrixFromFundamentalMatrix(K, fundamentalMatrix)
        
        C_s, R_s = ExtractCameraPose(essentialMatrix)

        C_O = np.zeros((3,1))
        R_O = np.identity(3)

        linearDepthPts = []
        for i in range(len(R_s)):
            points = LinearTriangulation(K, C_O, R_O, C_s[i], R_s[i], best_points1, best_points2)
            linearDepthPts.append(points)
            
        C, R, linearDepth = DisambiguateCameraPose(C_s, R_s, linearDepthPts)
        Poses[0].append(R)
        Poses[1].append(C)
        X0 = linearDepth
    
        linearDepthPts = LinearTriangulation(K, C_O, R_O, C, R, best_points1, best_points2)
        P = GetProjectionMatrix(C, R, K)
        U_pred = World2Image(X0, P)
        ErrorPreOpt = ReprojectionError(U_pred, best_points2)
        
        # print(f"Error Pre-Optimization: {ErrorPreOpt.mean()}")
        
        

        nonlinearDepthPts = NonLinearTriangulation(X0, K, C_O, R_O, C, R, best_points1, best_points2)
        
        TotalDepthPoints.append(nonlinearDepthPts)
        
        
    print(Poses)
    
    Plot3DPointSets(TotalDepthPoints, ['brown','blue','pink','purple'], ['Pose 1', 'Pose 2', 'Pose 3', 'Pose 4'], 
                    [-30, 30], [-30, 30], 'points from all poses')
        
        

    # """WIP
    # # Images 2-5
    # for img_num in range(3, 6):

    #     coord_pair = np.array(returnpairs(Matchpairs, [1,img_num]))
    #     coordpairs1 = coord_pair[:,0,:] #[pair[0] for pair in coord_pair]
    #     coordpairs2 = coord_pair[:,1,:] #[pair[0] for pair in coord_pair]

    #     best_points_1_1, best_points_1_i = OutlierRejectionRANSAC(coordpairs1, coordpairs2, break_percentage=0.9)

    #     u_v_1_12 = best_points1
    #     u_v_1_1i = best_points_1_1
    #     u_v_1_i = best_points_1_i

    #     uv_1i, world_points_1_i = find_matching_points(X_points_corrected, u_v_1_12, u_v_1_1i, u_v_1_i)

    #     #

    #     R_new, C_new = PnP_RANSAC(K, uv_1i, world_points_1_i)

    #     if np.linalg.det(R_new) < 0:    # enforce right-hand coordinate system
    #         R_new = -R_new
    #         C_new = -C_new

    #     R_opt, C_opt = nonlinear_PnP(K, uv_1i, world_points_1_i, R_new, C_new)

    #     R_set.append(R_opt)
    #     C_set.append(C_opt)

    #     X_new_linear = linear_triangulation(K, C_opt, R_opt, best_matched_points_1_i)
    #     X_points_nonlin = non_linear_triangulation(K, C_opt, R_opt, best_matched_points_1_i, X_new_linear)
    #     X_points_set.append(X_points_nonlin)

    #     # Visibility matrix
    #     # V = build_visibility_matrix(X_points_set[0], feature_flags, image_num, idx)
    #     # print("V mat for image ", str(image_num), " : ", V)

    # visualize_points_camera_poses(X_points_set[0], R_set, C_set)
    # """
            
        
    
    
    
    
    
if __name__ == "__main__":
	main()