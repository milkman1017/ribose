import numpy as np 
import json 
from openmm.unit import *
import glob
import matplotlib.pyplot as ax
from tqdm import tqdm as pbar
from mpl_toolkits.mplot3d import Axes3D
from pylab import *
import ripser
import mdtraj as md
import argparse
from scipy.stats import gaussian_kde
from scipy.fft import fft, ifft
import seaborn as sns
import configparser

def get_config():
    config = configparser.ConfigParser()
    config.read('analysis_config.ini')
    return config

def compute_heights(traj):
    sheet_atoms = traj.topology.select('resn "G" or resn "C"')
    try:
        dribose_atoms = traj.topology.select('resn "DRI"')
        if len(dribose_atoms) > 0:
            dribose_heights = md.compute_distances(traj, np.array([[sheet_atom, dribose_atom] for sheet_atom in sheet_atoms for dribose_atom in dribose_atoms]))[:, 0]
        else:
            print('No D-ribose in this sim')
            dribose_heights = None
    except:
        print('No D-ribose in this sim')
        dribose_heights = None
    
    try:
        lribose_atoms = traj.topology.select('resn "LRI"')
        if len(lribose_atoms) > 0:
            lribose_heights = md.compute_distances(traj, np.array([[sheet_atom, lribose_atom] for sheet_atom in sheet_atoms for lribose_atom in lribose_atoms]))[:, 0]
        else:
            print('No L-ribose in this sim')
            lribose_heights = None
    except:
        print('No L-ribose in this sim')
        lribose_heights = None
    
    return dribose_heights, lribose_heights

def graph_heights(dribose_heights, lribose_heights):
    dribose_heights = np.array(dribose_heights)
    lribose_heights = np.array(lribose_heights)

    fig, ax = plt.subplots()

    sns.kdeplot(data=dribose_heights, linewidth=1, color='b', label='D-Ribose')
    sns.kdeplot(data=lribose_heights, linewidth=1, color='r', label='L-Ribose')
    ax.legend(['D-Ribose','L-Ribose'])
    ax.set_xlabel('Height Above Sheet (nm)')
    ax.set_ylabel('PDF')
    ax.set_title('Probability Density of height of ribose')
    plt.show()

def compute_hbonds(chunk, hbond_counts):

    D_G,D_C,D_B,L_G,L_C,L_B,D_D,D_L,L_L = [],[],[],[],[],[],[],[],[]

    for frame in chunk:
        DG = 0
        DC = 0
        LG = 0
        LC = 0
        DD = 0
        DL = 0
        LL = 0
        hbonds = md.baker_hubbard(frame,exclude_water=True)
        
        #get hbond counts 
        for hbond in hbonds:
            atom1, atom2 = hbond[0], hbond[2]
            res1, res2 = frame.topology.atom(atom1).residue, frame.topology.atom(atom2).residue
            atom1_index, atom2_index = frame.topology.atom(atom1).index % res1.n_atoms, frame.topology.atom(atom2).index % res2.n_atoms

            if (res1.name == 'G' and res2.name == 'DRI') or (res1.name == 'DRI' and res2.name == 'G'):
                DG += 1
            elif (res1.name == 'C' and res2.name == 'DRI') or (res1.name == 'DRI' and res2.name == 'C'):
                DC+= 1
            elif (res1.name == 'G' and res2.name == 'LRI') or (res1.name == 'LRI' and res2.name == 'G'):
                LG += 1
            elif (res1.name == 'C' and res2.name == 'LRI') or (res1.name == 'LRI' and res2.name == 'C'):
                LC += 1
            elif (res1.name == 'DRI' and res2.name == 'DRI'):
                DD += 1
            elif (res1.name == 'DRI' and res2.name == 'LRI') or (res1.name == 'LRI' and res2.name == 'DRI'):
                DL += 1
            elif (res1.name == 'LRI' and res2.name == 'LRI'):
                LL += 1

            hbond_key = f'{res1.name}-{res2.name}'
            hbond_count_key = f"{atom1_index}-{atom2_index}"

            if hbond_key not in hbond_counts:
                hbond_counts[hbond_key] = dict()
            if hbond_count_key not in hbond_counts[hbond_key]:
                hbond_counts[hbond_key][hbond_count_key]=0
            hbond_counts[hbond_key][hbond_count_key] += 1

        D_G.append(DG)
        D_C.append(DC)
        D_B.append(DG+DC)
        L_G.append(LG)
        L_C.append(LC)
        L_B.append(LG+LC)
        D_D.append(DD)
        D_L.append(DL)
        L_L.append(LL)
            
    return hbond_counts, D_G, D_C, D_B, L_G, L_C, L_B, D_D, D_L, L_L

def ribose_label_sort(item):
    if item.startswith('DRI'):
        return (0, int(item[3:]))
    elif item.startswith('LRI'):
        return (1, int(item[3:]))
    elif item.startswith('C'):
        return (2, int(item[1:]))
    elif item.startswith('G'):
        return (3, int(item[1:]))
    else:
        return (4, int(item[2:]))

def hbond_heatmap(hbond_counts):

    dribose_donor_labels = set()
    dribose_acceptor_labels = set()

    lribose_donor_labels = set()
    lribose_acceptor_labels = set()

    hbonds = hbond_counts

    for residue, bond_dict in hbonds.items():
        if residue == 'DRI-G' or residue == 'DRI-C' or residue == 'G-DRI' or residue == 'C-DRI':
            donor_residue, acceptor_residue = residue.split('-')
            for atom in bond_dict.keys():
                dribose_donor_labels.add(f"{donor_residue}-{atom.split('-')[0]}")
                dribose_acceptor_labels.add(f"{acceptor_residue}-{atom.split('-')[1]}")

        elif residue == 'LRI-C' or residue == 'LRI-G' or residue == 'G-LRI' or residue == 'C-LRI':
            donor_residue, acceptor_residue = residue.split('-')
            for atom in bond_dict.keys():
                lribose_donor_labels.add(f"{donor_residue}-{atom.split('-')[0]}")
                lribose_acceptor_labels.add(f"{acceptor_residue}-{atom.split('-')[1]}")

    dribose_donor_labels = sorted(dribose_donor_labels, key=ribose_label_sort)
    dribose_acceptor_labels = sorted(dribose_acceptor_labels, key=ribose_label_sort,reverse=True)

    lribose_donor_labels = sorted(lribose_donor_labels,key=ribose_label_sort)
    lribose_acceptor_labels = sorted(lribose_acceptor_labels, key=ribose_label_sort,reverse=True)
    
    dribose_bond_data = np.zeros((len(dribose_donor_labels), len(dribose_acceptor_labels)))
    lribose_bond_data = np.zeros((len(lribose_donor_labels), len(lribose_acceptor_labels)))
    
    for residue, bond_dict in hbonds.items():
        if residue == 'DRI-G' or residue == 'DRI-C' or residue == 'G-DRI' or residue == 'C-DRI':
            donor_residue, acceptor_residue = residue.split('-')

            for atom, count in bond_dict.items():
                donor, acceptor = atom.split('-')
                donor_label = f"{donor_residue}-{donor}"
                acceptor_label = f"{acceptor_residue}-{acceptor}"
                donor_index = dribose_donor_labels.index(donor_label)
                acceptor_index = dribose_acceptor_labels.index(acceptor_label)
                dribose_bond_data[donor_index, acceptor_index] += count

        elif residue == 'LRI-C' or residue == 'LRI-G' or residue == 'G-LRI' or residue == 'C-LRI':
            donor_residue, acceptor_residue = residue.split('-')
            for atom, count in bond_dict.items():
                donor, acceptor = atom.split('-')
                donor_label = f"{donor_residue}-{donor}"
                acceptor_label = f"{acceptor_residue}-{acceptor}"
                donor_index = lribose_donor_labels.index(donor_label)
                acceptor_index = lribose_acceptor_labels.index(acceptor_label)
                lribose_bond_data[donor_index, acceptor_index] += count

    fig, ax = plt.subplots(1,2)
    im1 = ax[0].imshow(dribose_bond_data, cmap="hot")

    ax[0].set_xticks(np.arange(len(dribose_acceptor_labels)))
    ax[0].set_xlabel('Acceptors')
    ax[0].set_yticks(np.arange(len(dribose_donor_labels)))
    ax[0].set_xticklabels(dribose_acceptor_labels)
    ax[0].set_yticklabels(dribose_donor_labels)
    ax[0].set_ylabel('Donors')
    ax[0].set_title('D-Ribose Contact Map')

    im2 = ax[1].imshow(lribose_bond_data, cmap='hot')
    ax[1].set_xticks(np.arange(len(lribose_acceptor_labels)))
    ax[1].set_xlabel('Acceptors')
    ax[1].set_yticks(np.arange(len(lribose_donor_labels)))
    ax[1].set_xticklabels(lribose_acceptor_labels)
    ax[1].set_yticklabels(lribose_donor_labels)
    ax[1].set_ylabel('Donors')
    ax[1].set_title('L-Ribose Contact Map')

    plt.setp(ax[0].get_xticklabels(), rotation=45, ha="right", rotation_mode="anchor")
    plt.setp(ax[1].get_xticklabels(), rotation=45, ha="right", rotation_mode="anchor")
    
    plt.tight_layout()
    plt.suptitle('Hydrogen Bond Heat Map')
    plt.show()

def hbond_order(D_G,D_C,D_B,L_G,L_C,L_B,D_D,D_L,L_L):
    D_G = np.mean(D_G,axis=0)/12
    D_C = np.mean(D_C, axis=0)/12
    D_B = np.mean(D_B, axis=0)/12
    L_G = np.mean(L_G, axis=0)/18
    L_C = np.mean(L_C, axis=0)/18
    L_B = np.mean(L_B, axis=0)/18
    D_D = np.mean(D_D, axis=0)/12
    D_L = np.mean(D_L, axis=0)/30
    L_L = np.mean(L_L, axis=0)/18

    time = np.arange(len(D_G)) * 0.004

    fig, ax = plt.subplots(3,3)
    ax[0,0].plot(time, D_G, linewidth=1, color='b', label='D-Ribose')
    ax[0,0].plot(time, L_G, linewidth=1, color='r', label='L-Ribose')
    ax[0,0].set_title('Guanine H-Bonds')
    ax[0,0].set_xlabel('Time (ns)')
    ax[0,0].set_ylabel('Count')

    ax[1,0].plot(time, D_C, linewidth=1, color='b', label='D-Ribose')
    ax[1,0].plot(time, L_C, linewidth=1, color='r', label='L-Ribose')
    ax[1,0].set_title('Cytosine H-Bonds')
    ax[1,0].set_xlabel('Time (ns)')
    ax[1,0].set_ylabel('Count')

    ax[2,0].plot(time, D_B, linewidth=1, color='b', label='D-Ribose')
    ax[2,0].plot(time, L_B, linewidth=1, color='r', label='L-Ribose')
    ax[2,0].set_title('Guanine and Cytosine H-Bonds')
    ax[2,0].set_xlabel('Time (ns)')
    ax[2,0].set_ylabel('Count')


    ax[0,1].hist(D_G, histtype='step', density=True, bins='auto', color='b', label='D-Ribose')
    ax[0,1].hist(L_G, histtype='step', density=True, bins='auto', color='r', label='L-Ribose')
    ax[0,1].set_title('Distribution of Guanine H-Bonds')
    ax[0,1].set_xlabel('Number of H-Bonds')

    ax[1,1].hist(D_C, histtype='step', density=True, bins='auto', color='b', label='D-Ribose')
    ax[1,1].hist(L_C, histtype='step', density=True, bins='auto', color='r', label='L-Ribose')
    ax[1,1].set_title('Distribution of Cytosine H-Bonds')
    ax[1,1].set_xlabel('Number of H-Bonds')

    ax[2,1].hist(D_B, histtype='step', density=True, bins='auto', color='b', label='D-Ribose')
    ax[2,1].hist(L_B, histtype='step', density=True, bins='auto', color='r', label='L-Ribose')
    ax[2,1].set_title('Distribution of Sheet H-Bonds')
    ax[2,1].set_xlabel('Number of H-Bonds')

    ax[0,2].plot(time, D_D, linewidth=1, color='b', label='D-Ribose')
    ax[0,2].plot(time, L_L, linewidth=1, color='r', label='L-Ribose')
    ax[0,2].set_title('Self-Ribose H-Bonds')
    ax[0,2].set_xlabel('Time (ns)')
    ax[0,2].set_ylabel('Count')

    ax[1,2].plot(time, D_L, linewidth=1, color='m')
    ax[1,2].set_title('D to L Ribose H-Bonds')
    ax[1,2].set_xlabel('Time (ns)')
    ax[1,2].set_ylabel('Count')

    plt.legend()
    plt.tight_layout()
    plt.show()

def nematic_order(traj):
    dribose_indices_list = []  
    lribose_indices_list = []  

    for residue in traj.topology.residues:
        if residue.name == 'DRI':
            dribose_indices = [atom.index for atom in residue.atoms]
            dribose_indices_list.append(dribose_indices) 
        elif residue.name == 'LRI':
            lribose_indices = [atom.index for atom in residue.atoms]
            lribose_indices_list.append(lribose_indices) 

    dribose_order_list = [] 
    lribose_order_list = []  

    for dribose_indices in dribose_indices_list:
        dribose_order = md.compute_nematic_order(traj, indices=dribose_indices_list)
        dribose_order_list.append(dribose_order) 

    for lribose_indices in lribose_indices_list:
        lribose_order = md.compute_nematic_order(traj, indices=lribose_indices_list)
        lribose_order_list.append(lribose_order)

    dribose_order_list = np.mean(dribose_order_list, axis=0)
    lribose_order_list = np.mean(lribose_order_list, axis=0)

    return dribose_order_list, lribose_order_list

def graph_nematic_order(dribose_order, lribose_order):
    dribose_order = np.mean(dribose_order, axis=0)
    lribose_order = np.mean(lribose_order, axis=0)

    time = np.arange(len(dribose_order)) * 0.004

    fig, ax = plt.subplots(2,1)
    ax[0].plot(time, dribose_order, color='b', linewidth=1, label='D-ribose')
    ax[0].plot(time, lribose_order, color='r', linewidth=1, label='L-ribose')
    ax[0].set_xlabel('Time (ns)')
    ax[0].set_ylabel('Nematic Order Parameter')
    ax[0].legend()

    ax[1].hist(dribose_order, color='blue', histtype='step', label='D-Ribose',density=True, bins='auto')
    ax[1].hist(lribose_order, color='r', histtype='step', label='L-ribose',density=True, bins='auto')
    ax[1].set_xlabel('Nematic Order Parameter')
    ax[1].legend()
    
    plt.suptitle('Nematic Order of Ribose Enantiomers')
    plt.show()

def sasa(traj):
    DRI_res_indices = []
    LRI_res_indices = []

    for residue in traj.topology.residues: 
        if residue.name == 'DRI':
            DRI_res_indices.append(residue.index)
        elif residue.name == 'LRI':
            LRI_res_indices.append(residue.index)

    sasa = md.shrake_rupley(traj, mode='residue')
    
    DRI_sasa = sasa[:, DRI_res_indices]
    LRI_sasa = sasa[:, LRI_res_indices]

    return DRI_sasa, LRI_sasa

def autocorr(x):
    "Compute an autocorrelation with numpy"
    x = x - np.mean(x)
    result = np.correlate(x, x, mode='full')
    result = result[result.size//2:]
    return result / result[0]

def graph_sasa(DRI_sasa, LRI_sasa):
    DRI_sasa = np.array(DRI_sasa)
    LRI_sasa = np.array(LRI_sasa)

    DRI_sasa_tot_sims = np.concatenate(DRI_sasa, axis=1)
    LRI_sasa_tot_sims = np.concatenate(LRI_sasa, axis=1)

    DRI_sasa_tot =np.concatenate(DRI_sasa_tot_sims)
    LRI_sasa_tot = np.concatenate(LRI_sasa_tot_sims)

    sns.kdeplot(data=DRI_sasa_tot, linewidth=1, color='b', label='D-Ribose')
    sns.kdeplot(data=LRI_sasa_tot, linewidth=1, color='r', label='L-Ribose')
    plt.yscale('log')
    plt.xlabel('Solvent Accessible Surface Area (nm^2)')
    plt.ylabel('log density')
    plt.title('KDE of SASA')
    plt.legend()
    plt.show()

def main():
    config = get_config()
    sims = int(config.get('Input Setup','number sims'))
    sim_length = int(config.get('Input Setup','number steps'))
    lconc = int(config.get('Input Setup','lconc'))

    indir = config.get('Input Setup','input directory')
    outdir = config.get('Output Parameters','output directory')


    dribose_heights, lribose_heights = [],[]
    dribose_order, lribose_order = [],[]
    sim_DRI_sasa, sim_LRI_sasa = [],[]
    sim_D_G, sim_D_C, sim_D_B, sim_L_G, sim_L_C, sim_L_B, sim_D_D, sim_D_L, sim_L_L = [],[],[],[],[],[],[],[],[]
    hbond_counts = dict()

    for sim_number in range(sims):
        print('Analyzing sim number', sim_number)

        traj = md.iterload(f'{indir}/traj_{sim_number}_lconc_18_steps_{sim_length}.dcd', 
                            top=f'{indir}/topology_{sim_number}_lconc_18_steps_{sim_length}.pdb')
        
        traj_d_order, traj_l_order = [],[]
        traj_DRI_sasa, traj_LRI_sasa = [],[]
        D_G,D_C,D_B,L_G,L_C,L_B,D_D,D_L,L_L = [],[],[],[],[],[],[],[],[]
        for chunk in traj:

            dheight, lheight = compute_heights(chunk)
            dribose_heights.extend(dheight)
            lribose_heights.extend(lheight)

            # hbond_counts, traj_D_G, traj_D_C, traj_D_B, traj_L_G, traj_L_C, traj_L_B, traj_D_D, traj_D_L, traj_L_L = compute_hbonds(chunk,hbond_counts)
        #     D_G.extend(traj_D_G)
        #     D_C.extend(traj_D_C)
        #     D_B.extend(traj_D_B)
        #     L_G.extend(traj_L_G)
        #     L_C.extend(traj_L_C)
        #     L_B.extend(traj_L_B)
        #     D_D.extend(traj_D_D)
        #     D_L.extend(traj_D_L)
        #     L_L.extend(traj_L_L)

        #     traj_d_ord, traj_l_ord = nematic_order(chunk)
        #     traj_d_order.extend(traj_d_ord)
        #     traj_l_order .extend(traj_l_ord)

            # DRI_sasa, LRI_sasa = sasa(chunk)
            # traj_DRI_sasa.extend(DRI_sasa)
            # traj_LRI_sasa.extend(LRI_sasa)


        # sim_D_G.append(D_G)
        # sim_D_C.append(D_C)
        # sim_D_B.append(D_B)
        # sim_L_G.append(L_G)
        # sim_L_C.append(L_C)
        # sim_L_B.append(L_B)
        # sim_D_D.append(D_D)
        # sim_D_L.append(D_L)
        # sim_L_L.append(L_L)

        # dribose_order.append(traj_d_order)
        # lribose_order.append(traj_l_order)

        # sim_DRI_sasa.append(traj_DRI_sasa)
        # sim_LRI_sasa.append(traj_LRI_sasa)


    # graph_sasa(sim_DRI_sasa, sim_LRI_sasa)
    # hbond_heatmap(hbond_counts)
    # hbond_order(sim_D_G,sim_D_C,sim_D_B,sim_L_G,sim_L_C,sim_L_B,sim_D_D,sim_D_L,sim_L_L)
    # graph_nematic_order(dribose_order, lribose_order)
    graph_heights(dribose_heights, lribose_heights)
    print(hbond_counts)

if __name__ == '__main__':
    main()