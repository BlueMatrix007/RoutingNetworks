"""
This file defines some simple experiments to illustrate how Pytorch-Routing functions.
"""
import numpy as np
import tqdm
import torch
from PytorchRouting.DecisionLayers import REINFORCE, QLearning, SARSA, ActorCritic, GumbelSoftmax, PerTaskAssignment, \
    WPL, AAC, AdvantageLearning, RELAX, EGreedyREINFORCE, EGreedyAAC
from PytorchRouting.Examples.Models import PerTask_all_fc, RoutedAllFC, PerTask_1_fc, PerDecisionSingleAgent, \
    Dispatched
from PytorchRouting.Examples.Datasets import CIFAR100MTL


def compute_batch(model, batch):
    samples, labels, tasks = batch
    out, meta = model(samples, tasks=tasks)
    correct_predictions = (out.max(dim=1)[1].squeeze() == labels.squeeze()).cpu().numpy()
    accuracy = correct_predictions.sum()
    oh_labels = one_hot(labels, out.size()[-1])
    module_loss, decision_loss = model.loss(out, meta, oh_labels)
    return module_loss, decision_loss, accuracy

def one_hot(indices, width):
    indices = indices.squeeze().unsqueeze(1)
    oh = torch.zeros(indices.size()[0], width).to(indices.device)
    oh.scatter_(1, indices, 1)
    return oh


def run_experiment(model, dataset, learning_rates, routing_module_learning_rate_ratio):
    print('Loaded dataset and constructed model. Starting Training ...')
    for epoch in range(50):
        optimizers = []
        parameters = []
        if epoch in learning_rates:
            try:
                optimizers.append(torch.optim.SGD(model.routing_parameters(),
                                                  lr=routing_module_learning_rate_ratio*learning_rates[epoch]))
                optimizers.append(torch.optim.SGD(model.module_parameters(),
                                                  lr=learning_rates[epoch]))
                parameters = model.module_parameters() + model.module_parameters()
            except AttributeError:
                optimizers.append(torch.optim.SGD(model.parameters(), lr=learning_rates[epoch]))
                parameters = model.parameters()
        train_log, test_log = np.zeros((3,)), np.zeros((3,))
        train_samples_seen, test_samples_seen = 0, 0
        dataset.enter_train_mode()
        model.train()
        # while True:
        pbar = tqdm.tqdm(unit=' samples')
        while True:
            try:
                batch = dataset.get_batch()
            except StopIteration:
                break
            train_samples_seen += len(batch[0])
            pbar.update(len(batch[0]))
            module_loss, decision_loss, accuracy = compute_batch(model, batch)
            (module_loss + decision_loss).backward()
            torch.nn.utils.clip_grad_norm_(parameters, 40., norm_type=2)
            for opt in optimizers:
                opt.step()
            model.zero_grad()
            train_log += np.array([module_loss.tolist(), decision_loss.tolist(), accuracy])
        pbar.close()
        dataset.enter_test_mode()
        model.eval()
        model.start_logging_selections()
        while True:
            try:
                batch = dataset.get_batch()
            except StopIteration:
                break
            test_samples_seen += len(batch[0])
            module_loss, decision_loss, accuracy = compute_batch(model, batch)
            test_log += np.array([module_loss.tolist(), decision_loss.tolist(), accuracy])
        print('Epoch {} finished after {} train and {} test samples..\n'
              '    Training averages: Model loss: {}, Routing loss: {}, Accuracy: {}\n'
              '    Testing averages:  Model loss: {}, Routing loss: {}, Accuracy: {}'.format(
            epoch + 1, train_samples_seen, test_samples_seen,
            *(train_log/train_samples_seen).round(3), *(test_log/test_samples_seen).round(3)))
        model.stop_logging_selections_and_report()


if __name__ == '__main__':
    # MNIST
    # dataset = MNIST_MTL(64, data_files=['./Datasets/mnist.pkl.gz'])
    # model = PerTask_all_fc(1, 288, 2, dataset.num_tasks, dataset.num_tasks)
    # model = WPL_routed_all_fc(1, 288, 2, dataset.num_tasks, dataset.num_tasks)
    cuda = False
    # cuda = True

    # CIFAR
    dataset = CIFAR100MTL(10, data_files=['./Datasets/cifar-100-py/train', './Datasets/cifar-100-py/test'], cuda=cuda)
    model = RoutedAllFC(WPL, 3, 128, 5, dataset.num_tasks, dataset.num_tasks)
    # model = RoutedAllFC(RELAX, 3, 128, 5, dataset.num_tasks, dataset.num_tasks)
    # model = RoutedAllFC(EGreedyREINFORCE, 3, 128, 5, dataset.num_tasks, dataset.num_tasks)
    # model = RoutedAllFC(AdvantageLearning, 3, 128, 5, dataset.num_tasks, dataset.num_tasks)
    # model = PerDecisionSingleAgent(AdvantageLearning, 3, 128, 5, dataset.num_tasks, dataset.num_tasks)
    # model = Dispatched(AdvantageLearning, 3, 128, 5, dataset.num_tasks, dataset.num_tasks)

    learning_rates = {0: 3e-3, 5: 1e-3, 10: 3e-4}
    routing_module_learning_rate_ratio = 0.3
    if cuda:
        model.cuda()
    run_experiment(model, dataset, learning_rates, routing_module_learning_rate_ratio)

'''
WPL_routed_all_fc(3, 512, 5, dataset.num_tasks, dataset.num_tasks)
    Training averages: Model loss: 0.427, Routing loss: 8.864, Accuracy: 0.711
    Testing averages:  Model loss: 0.459, Routing loss: 9.446, Accuracy: 0.674
'''
