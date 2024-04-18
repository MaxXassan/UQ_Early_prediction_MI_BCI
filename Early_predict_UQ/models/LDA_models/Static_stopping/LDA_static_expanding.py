import os
import sys
import numpy as np
import matplotlib.pyplot as plt
from sklearn.discriminant_analysis import LinearDiscriminantAnalysis
from sklearn.model_selection import KFold
from mne.decoding import CSP

from sklearn.model_selection import ParameterSampler
import numpy as np


current_directory = os.path.abspath('')

project_root = current_directory

sys.path.append(project_root)

print("ROOT:", project_root)
from Early_predict_UQ.data.make_dataset import make_data


# epoch tmin  = 2 and tmax = 6 , as the motor imagery task lasted in that time
def run_expanding_classification(subjects, initial_window_length, expansion_rate, csp_components):
    scores_across_subjects = []
    subjects_accuracies =[]

    current_person = 0
    for person in subjects:
        current_person += 1
        print("Person %d" % (person))
        subject= [person]
        epochs, labels = make_data(subject)
        epochs_data = epochs.get_data(copy=False)

        kf = KFold(n_splits=10, shuffle=True, random_state=42)
        scores_cv_splits = []

        lda = LinearDiscriminantAnalysis()
        csp = CSP(n_components= csp_components, reg=None, log=True, norm_trace=False)
        current_cv = 0 
        for train_idx, test_idx in kf.split(epochs_data):
            current_cv += 1
            y_train, y_test = labels[train_idx], labels[test_idx]
            X_train = csp.fit_transform(epochs_data[train_idx], y_train)
            lda.fit(X_train, y_train)
            w_start = np.arange(0, epochs_data.shape[2] - initial_window_length, expansion_rate) 
            scores_across_epochs = []
            for n, window_start in enumerate(w_start):
                window_length = initial_window_length + n * expansion_rate
                X_test_window = csp.transform(epochs_data[test_idx][:, :,  window_start:(window_start + window_length)])
                score = lda.score(X_test_window, y_test)
                scores_across_epochs.append(score)
            if current_cv == 1:
                scores_cv_splits = np.array(scores_across_epochs)
            else:
                scores_cv_splits = np.vstack((scores_cv_splits,np.array(scores_across_epochs)))

        mean_scores_across_cv = np.mean(scores_cv_splits, axis=0)
        if current_person == 1:
            scores_across_subjects  = np.array(mean_scores_across_cv)
        else:
            scores_across_subjects = np.vstack((scores_across_subjects,np.array(mean_scores_across_cv)))
        subjects_accuracies.append(np.mean(mean_scores_across_cv))
    mean_scores_across_subjects = np.mean(scores_across_subjects, axis=0)
    accuracy = mean_scores_across_subjects

    return subjects_accuracies, accuracy

def create_parameterslist(sfreq):
    rng = np.random.RandomState(42)
    initial_window_length = np.round(rng.uniform(0.1, 1, 10), 1)
    expansion_rate = np.round(rng.uniform(0.1, 1, 10), 1)

    parameters = {  
    'csp_components': [2, 4, 6, 8, 10], 
    'initial_window_length': np.round(sfreq * initial_window_length).astype(int), 
    'expansion_rate':  np.round(sfreq * expansion_rate).astype(int)
    }

    parameters_list = list(ParameterSampler(parameters, n_iter=20, random_state=rng))
    return parameters_list


def hyperparameter_tuning (parameters_list, subjects):
    mean_accuracy = 0
    best_accuracy = 0
    for n, param_set in enumerate(parameters_list):
        csp_components = param_set['csp_components']
        initial_window_length = param_set['initial_window_length'] 
        expansion_rate =  param_set['expansion_rate']

        _ , accuracy = run_expanding_classification(subjects, initial_window_length, expansion_rate, csp_components)
        
        mean_accuracy = np.mean(accuracy)

        print(f"Iteration {n+1}/{len(parameters_list)}: Mean accuracy for parameters {param_set} is {mean_accuracy}")

        if mean_accuracy > best_accuracy:
            best_accuracy = mean_accuracy
            best_params = param_set

    return best_params, best_accuracy

def evaluate_and_plot(best_params, best_accuracy, accuracy,subjects_accuracies):
    print("Best params:", best_params)
    print("Best accuracy", best_accuracy)
    print("Classification accuracy:", np.mean(accuracy))
    accuracy_array = np.array(accuracy)
    subject_tuples = [(i+1, acc) for i, acc in enumerate(subjects_accuracies)]

    sorted_subjects = sorted(subject_tuples, key=lambda x: x[1], reverse=True)

    for subject, subject_accuracy in sorted_subjects:
        print(f"Subject {subject}: Accuracy {subject_accuracy}")

    labels, tmin = epochs_info(labels=True, tmin=True)

    class_balance = np.zeros(4)
    for i in range(4):
        class_balance[i] = np.mean(labels == i)
    class_balance = np.max(class_balance)

    plt.title("Accuracy over time")
    plt.xlabel("Prediction time")
    plt.ylabel("Classification accuracy")

    prediction_times = np.arange(0, epochs_data.shape[2] - best_params['initial_window_length'], best_params['expansion_rate'])
    prediction_times  = (prediction_times + (best_params['initial_window_length'] / tmin)) / sfreq + tmin

    plt.plot(prediction_times, accuracy_array)
    plt.axhline(class_balance, linestyle="-", color="k", label="Chance")
    plt.axvline(tmin, linestyle="--", color="k", label="Onset")
    plt.title('Accuracy over time: LDA - Static model - Expanding window')
    plt.legend()
    plt.grid(True)
    plt.savefig(project_root + '/reports/figures/cumulitive/LDA/static/lda_static_expanding_accuracy_over_time.png')
    plt.show()

def epochs_info(labels=False, tmin=False, length=False):
    global epochs_data
    global labels_data
    if labels or tmin or length:
        epochs, labels_data = make_data([1])
        epochs_data = epochs.get_data(copy=False)

    if labels and tmin:
        return labels_data, epochs.tmin
    elif labels and length:
        return labels_data, epochs_data.shape[2]
    elif tmin and length:
        return epochs.tmin, epochs_data.shape[2]
    elif labels:
        return labels_data
    elif tmin:
        return epochs.tmin
    elif length:
        return epochs_data.shape[2]
    else:
        raise ValueError("At least one of 'labels', 'tmin', or 'length' must be True.")


if __name__ == "__main__":
    subjects = [1, 2, 3, 4, 5, 6, 7, 8, 9]  # 9 subjects
    sfreq = 250      
    #Hyperparameter_tuning
    print("\n\n Hyperparameter tuning: \n\n")
    parameters_list = create_parameterslist(sfreq)
    best_params, best_accuracy = hyperparameter_tuning(parameters_list, subjects)
    
    #classify
    print("\n\n Classification: \n\n")
    subjects_accuracies, accuracy = run_expanding_classification(subjects, best_params['initial_window_length'], best_params['expansion_rate'], best_params['csp_components'])
    accuracy_array = np.array(accuracy)

    #evaluate and plot
    evaluate_and_plot(best_params, best_accuracy, accuracy,subjects_accuracies)
