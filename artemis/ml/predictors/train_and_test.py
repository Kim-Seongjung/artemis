# coding=utf-8
from collections import OrderedDict

import numpy as np
from artemis.general.mymath import softmax
from artemis.general.should_be_builtins import remove_duplicates
from artemis.general.tables import build_table
from artemis.ml.datasets.datasets import DataSet
from artemis.ml.tools.iteration import zip_minibatch_iterate_info, IterationInfo

__author__ = 'peter'

"""
All evaluation functions in here are of the form

score = evaluation_fcn(actual, target)

Where:
    score is a scalar
    actual is an (n_samples, ...) array
    target is an (n_samples, ....) array
"""


def train_online_predictor(predictor, training_set, minibatch_size, n_epochs = 1):
    """
    Train a predictor on the training set
    :param predictor: An IPredictor object
    :param training_set: A DataCollection object
    :param minibatch_size: An integer, or 'full' for full batch training
    :param n_epochs: Number of passes to make over the training set.
    """
    print 'Training Predictor %s...' % (predictor, )
    for (_, data, target) in training_set.minibatch_iterator(minibatch_size = minibatch_size, epochs = n_epochs, single_channel = True):
        predictor.train(data, target)
    print 'Done.'


def evaluate_predictor(predictor, test_set, evaluation_function):
    if isinstance(evaluation_function, str):
        evaluation_function = get_evaluation_function(evaluation_function)
    output = predictor.predict(test_set.input)
    score = evaluation_function(actual = output, target = test_set.target)
    return score



def get_evaluation_function(name):
    return {
        'mse': mean_squared_error,
        'mean_squared_error': mean_squared_error,
        'mean_l1_error': mean_l1_error,
        'percent_argmax_correct': percent_argmax_correct,
        'percent_argmax_incorrect': percent_argmax_incorrect,
        'percent_correct': percent_correct,
        'softmax_categorical_xe': softmax_categorical_xe
        }[name]


def mean_l1_error(actual, target):
    return np.mean(np.sum(np.abs(actual-target), axis=-1), axis=-1)


def mean_squared_error(actual, target):
    return np.mean(np.sum((actual-target)**2, axis = -1), axis = -1)


def softmax_categorical_xe(actual, target):
    """
    :param actual: An (n_samples, n_dims) array identifying pre-logistic output
    :param target: An (n_samples, ) integer array identifying labels
    :return:
    """
    if target.ndim==1:
        assert target.dtype==int and np.max(target) < actual.shape[1]
    elif target.ndim==2:
        assert np.all(target.sum(axis=1)==1) and np.all(np.max(target, axis=1)==1)
        target = np.argmax(target, axis=1)
    else:
        raise Exception("Don't know how to interpret a {}-D target".format(target))

    return np.mean(softmax(actual, axis=1)[np.arange(actual.shape[0]), target], axis=0)


def fraction_correct(actual, target):
    return np.mean(actual == target)


def percent_correct(actual, target):
    return 100*fraction_correct(actual, target)


def percent_argmax_correct(actual, target):
    """
    :param actual: An (n_samples, n_dims) array
    :param target: An (n_samples, ) array of indices OR an (n_samples, n_dims) array
    :return:
    """
    actual = collapse_onehot_if_necessary(actual)
    target = collapse_onehot_if_necessary(target)
    return 100*fraction_correct(actual, target)


def percent_binary_incorrect(actual, target):
    return 100.-percent_binary_correct(actual, target)


def percent_binary_correct(actual, target):
    """
    :param actual:  A (n_samples, ) array of floats between 0 and 1
    :param target: A (n_samples, ) array of True/False
    :return: The percent of times the "actual" was closes to the correct.
    """
    assert len(actual) == len(target)
    assert target.ndim==1
    if actual.ndim>1:
        assert actual.shape == (len(target), 1)
        actual = actual[:, 0]
    if np.array_equal(np.unique(target), (0, 1)):
        assert np.all(actual)>=0 and np.all(actual)<=1
        assert np.all((target==0)|(target==1))
        return 100*np.mean(np.round(actual) == target)
    elif np.array_equal(np.unique(target), (-1, 1)):
        assert np.all((target==-1)|(target==1))
        return 100*np.mean((actual>0)*2-1 == target)
    else:
        raise Exception("Go away I'm tired.")


def percent_argmax_incorrect(actual, target):
    return 100 - percent_argmax_correct(actual, target)


def collapse_onehot_if_necessary(output_data):
    """
    Given an input that could either be in onehot encoding or not, return it in onehot encoding.

    :param output_data: Either an (n_samples, n_dims) array, or an (n_samples, ) array of labels.
    :return: An (n_samples, ) array.
    """

    output_data = np.squeeze(output_data)

    if output_data.ndim == 2:
        return np.argmax(output_data, axis = 1)
    else:
        assert output_data.ndim == 1 and output_data.dtype in (int, 'int32', bool)
        return output_data


class ModelTestScore(object):
    """
    An object representing the evaluation of a model on
    - one or more test sets
    - one or more prediction functions
    - one or more costs
    """

    def __init__(self, ):
        self.scores = OrderedDict()

    def __getitem__(self, (data_subset, prediction_function_name, cost_name)):
        return self.scores[data_subset, prediction_function_name, cost_name]

    def __setitem__(self, (data_subset, prediction_function_name, cost_name), value):
        self.scores[data_subset, prediction_function_name, cost_name] = value

    def keys(self):
        return self.scores.keys()

    def values(self):
        return self.scores.values()

    def iteritems(self):
        return self.scores.iteritems()

    def get_score(self, subset=None, prediction_function=None, cost_name=None):
        if subset is None:
            subset = self.get_only_data_subset()
        if prediction_function is None:
            prediction_function = self.get_only_prediction_function()
        if cost_name is None:
            cost_name = self.get_only_cost()
        return self[subset, prediction_function, cost_name]

    def get_data_subsets(self):
        return remove_duplicates([s for s, _, _ in self.scores.keys()])

    def get_prediction_functions(self):
        return remove_duplicates([f for _, f, _ in self.scores.keys()])

    def get_costs(self):
        return remove_duplicates([c for _, c, c in self.scores.keys()])

    def get_only_data_subset(self):
        return self._get_only_element(self.get_data_subsets(), 'Data Subset')

    def get_only_prediction_function(self):
        return self._get_only_element(self.get_prediction_functions(), 'Prediction Function')

    def get_only_cost(self):
        return self._get_only_element(self.get_costs(), 'Cost')

    @staticmethod
    def _get_only_element(elements, category_name):
        if len(elements)==1:
            result, = elements
            return result
        else:
            raise Exception("You need to specify the {}.  Options are: {}".format(category_name, elements))

    def __str__(self):
        sections = [u'({}{}{})={}'.format(
            subset,
            '' if pred_fcn is None else ','+str(pred_fcn),
            ','+str(cost_fcn),
            self.get_score(subset, pred_fcn, cost_fcn))
            for subset, pred_fcn, cost_fcn in self.keys()
            ]
        return '{}:{}'.format(self.__class__.__name__, ','.join(sections))

    def get_table(self):
        # test_pair_names, function_names, cost_names = [remove_duplicates(k) for k in zip(*self.scores.keys())]
        rows = build_table(
            lookup_fcn=lambda (test_pair_name_, function_name_), cost_name_: self[test_pair_name_, function_name_, cost_name_],
            row_categories=[[test_pair_name for test_pair_name in self.get_data_subsets()], [function_name for function_name in self.get_prediction_functions()]],
            column_categories=[cost_name for cost_name in self.get_costs()],
            row_header_labels=['Subset', 'Function'],
            clear_repeated_headers=False,
            remove_unchanging_cols=True
        )
        import tabulate
        return tabulate.tabulate(rows)


class InfoScorePair(object):

    def __init__(self, info, score):
        """
        :param info: An IterationInfo Object
        :param v: A ModelTestScore object
        """
        assert isinstance(info, IterationInfo)
        assert isinstance(score, ModelTestScore)
        self.info = info
        self.score = score

    def __iter__(self):
        return iter([self.info, self.score])

    def __str__(self):
        return 'Epoch {} (after {:.3g}s)\n{}'.format(self.info.epoch, self.info.time, self.score)

    def get_table_headers(self):
        iterfields = IterationInfo._fields
        subset_names, prediction_funcs, cost_funcs = zip(*self.score.keys())
        return [
            (' ', )*len(iterfields) + subset_names,
            (' ', )*len(iterfields) + prediction_funcs,
            iterfields + cost_funcs
            ]

    def get_table_row(self):
        return [v for v in self.info] + self.score.values()

    def get_table(self, remove_headers = False):
        from tabulate import tabulate
        iterfields = IterationInfo._fields
        subset_names, prediction_funcs, cost_funcs = zip(*self.score.keys())
        headers = [
            (' ', )*len(iterfields) + subset_names,
            (' ', )*len(iterfields) + prediction_funcs,
            iterfields + cost_funcs
            ]
        data = [v for v in self.info] + self.score.values()
        table = tabulate(headers+[data], tablefmt='plain')
        if remove_headers:
            table = table[table.rfind('\n'):]

        return table

        # iterfields = IterationInfo._fields
        # subset_names, prediction_funcs, cost_funcs = zip(*self.score.keys())
        # return [
        #     (' ', )*len(iterfields) + subset_names,
        #     (' ', )*len(iterfields) + prediction_funcs,
        #     iterfields + cost_funcs
        #     ]



class InfoScorePairSequence(object):
    """
    An object representing a sequence of pairs of IterationInfo, Score objects.
    """

    def __init__(self):
        self._pairs = []

    def __iter__(self):
        return iter(self._pairs)

    def __getitem__(self, ix):
        return self._pairs[ix]

    def __len__(self):
        return len(self._pairs)

    def append(self, info_score_pair):
        self._pairs.append(info_score_pair)

    def get_oneliner(self, subset = 'test', prediction_function = None, score_measure = None, lower_is_better = False):
        """
        Return a 1-liner descibing the best score.
        """
        subset, prediction_function, score_measure = self._fill_fields(subset, prediction_function, score_measure)
        best_pair = self.get_best(subset, prediction_function, score_measure, lower_is_better=lower_is_better)
        return 'Best: Epoch {} of {}, {}: {}'.format(best_pair.info.epoch, self._pairs[-1].info.epoch, score_measure, best_pair.score[subset, prediction_function, score_measure])

    def get_values(self, subset = 'test', prediction_function = None, score_measure = None):
        return [score.get_score(subset, prediction_function, score_measure) for _, score in self]

    def get_best_value(self, subset = 'test', prediction_function = None, score_measure = None, lower_is_better = False):
        best_pair = self.get_best(subset, prediction_function, score_measure, lower_is_better=lower_is_better)
        return best_pair.score[subset, prediction_function, score_measure]

    def get_best(self, subset = 'test', prediction_function = None, score_measure = None, lower_is_better = False):
        """
        Given a list of (info, score) pairs which represet the progress over training, find the best score and return it.
        :param score_info_pairs: A list<(IterationInfo, dict)> of the type returned in train_and_test_online_predictor
        :param subset: 'train' or 'test' ... which subset to use to look for the best score
        :param prediction_function: Which prediction function (if there are multiple prediction functions, otherwise leave blank)
        :param score_measure: Which score measure (if there are multiple score measures, otherwise leave blank)
        :param lower_is_better: True if a lower score is better for the chosen score_measure
        :return: A InfoScorePair object
        """
        assert len(self._pairs) > 0, "You need to have at least one score to determine the best one."
        subset, prediction_function, score_measure = self._fill_fields(subset, prediction_function, score_measure)
        best_pair = self._pairs[0]
        for info_score_pair in self._pairs[1:]:
            best_pair = info_score_pair if (info_score_pair.score[subset, prediction_function, score_measure] < best_pair.score[subset, prediction_function, score_measure]) == lower_is_better else best_pair
        return best_pair

    def _fill_fields(self, subset = None, prediction_function = None, score_measure = None):
        first_score = self._pairs[0].score
        if subset is None:
            subset = first_score.get_only_data_subset()
        if prediction_function is None:
            prediction_function = first_score.get_only_prediction_function()
        if score_measure is None:
            score_measure = first_score.get_only_cost()
        return subset, prediction_function, score_measure

    def __str__(self):
        desc = 'InfoScorePairSequence<{} epochs over {}s. '.format(self[-1].info.epoch, self[-1].info.time)
        keys = self[0].score.keys()
        for subset, pred_fcn, cost_fcn in keys:
            values = self.get_values(subset, pred_fcn, cost_fcn)
            desc+=',({}{}{}) in [{} to {}]'.format(subset, '' if pred_fcn is None else ','+str(pred_fcn), ','+str(cost_fcn), min(values), max(values))
        desc += '>'
        return desc

    def get_table(self):
        from tabulate import tabulate
        if len(self)==0:
            return repr(self) + '\n' + '<Empty>'
        else:
            rows = self[0].get_table_header() + [pair.get_table_row() for pair in self]
            return repr(self)+'\n  '+tabulate(rows).replace('\n', '\n  ')


def assess_prediction_functions(test_pairs, functions, costs, print_results=False):
    """

    :param test_pairs: A list<pair_name, (x, y)>, where x, y are equal-length vectors representing the samples in a dataset.
        Eg. [('training', (x_train, y_train)), ('test', (x_test, y_test))]
    :param functions: A list<function_name, function> of functions for computing the forward pass.
    :param costs: A list<cost_name, cost_function> of cost functions, where cost_function has the form:
        cost = cost_fcn(guess, y), where cost is a scalar, and guess is the output of the prediction function given one
            of the inputs (x) in test_pairs.
    :return: A ModelTestScore object
    """
    if isinstance(test_pairs, DataSet):
        test_pairs = [
            ('train', (test_pairs.training_set.input, test_pairs.training_set.target)),
            ('test', (test_pairs.test_set.input, test_pairs.test_set.target)),
            ]
    assert isinstance(test_pairs, list)
    assert all(len(_)==2 for _ in test_pairs)
    assert all(len(pair)==2 for name, pair in test_pairs)
    if callable(functions):
        functions = [(functions.__name__ if hasattr(functions, '__name__') else None, functions)]
    else:
        assert all(callable(f) for name, f in functions)
    if callable(costs):
        costs = [(costs.__name__, costs)]
    elif isinstance(costs, basestring):
        costs = [(costs, get_evaluation_function(costs))]
    else:
        costs = [(cost, get_evaluation_function(cost)) if isinstance(cost, basestring) else (cost.__name__, cost) if callable(cost) else cost for cost in costs]
    assert all(callable(cost) for name, cost in costs)

    results = ModelTestScore()
    for test_pair_name, (x, y) in test_pairs:
        for function_name, function in functions:
            for cost_name, cost_function in costs:
                results[test_pair_name, function_name, cost_name] = cost_function(function(x), y)

    if print_results:
        print results.get_table()

    return results


def print_score_results(score, info=None):
    """
    :param results: An OrderedDict in the format returned by assess_prediction_functions.
    :return:
    """
    if info is not None:
        print 'Epoch {} (after {:.3g}s)'.format(info.epoch, info.time)
    test_pair_names, function_names, cost_names = [remove_duplicates(k) for k in zip(*score.keys())]
    rows = build_table(
        lookup_fcn=lambda (test_pair_name_, function_name_), cost_name_: score[test_pair_name_, function_name_, cost_name_],
        row_categories = [[test_pair_name for test_pair_name in test_pair_names], [function_name for function_name in function_names]],
        column_categories = [cost_name for cost_name in cost_names],
        row_header_labels=['Subset', 'Function'],
        clear_repeated_headers = False,
        remove_unchanging_cols=True
        )
    import tabulate
    print tabulate.tabulate(rows)


def train_and_test_online_predictor(dataset, train_fcn, predict_fcn, minibatch_size, n_epochs=None, test_epochs=None,
            score_measure='percent_argmax_correct', test_callback=None, training_callback = None, score_collection = None):
    """
    Train an online predictor.  Return a data structure with info about the training.
    :param dataset: A DataSet object
    :param train_fcn: A function of the form train_fcn(x, y) which updates the parameters
    :param predict_fcn: A function of the form y=predict_fcn(x) which makes a prediction giben inputs
    :param minibatch_size: Minibatch size
    :param n_epochs: Number of epoch
    :param test_epochs: Test epcohs
    :param score_measure: String or function of the form:
        score = score_measure(guess, ground_truth)
        To be used in testing.
    :param test_callback: Function to be called on test.  It has the form: f(info, score)
    :param training_callback: Function to be called after every training iteration.  It has the form f(info, x, y) where
    :param score_collection: If not None, a InfoScoreCollection object into which you save scores.  This allows you to
        access the scores before this function returns.
    :return: A list<info, scores>  where...
        IterationInfo object (see artemis.ml.tools.iteration.py) with fields:
            'iteration', 'epoch', 'sample', 'time', 'test_now', 'done'
        scores is dict<(subset, prediction_function, cost_function) -> score>  where:
            subset is a string identifying the subset (eg 'train', 'test')
            prediction_function is identifies the prediction function (usually None, but can be used if you specify multiple prediction functions)
            cost_function is identifiers the cost function.
    """
    info_score_pairs = InfoScorePairSequence() if score_collection is None else score_collection
    for (x_mini, y_mini), info in zip_minibatch_iterate_info(dataset.training_set.xy, minibatch_size=minibatch_size, n_epochs=n_epochs, test_epochs=test_epochs):
        if info.test_now:
            rate = (info.time-last_time)/(info.epoch - last_epoch) if info.epoch>0 else float('nan')
            print 'Epoch {}.  Rate: {:.3g}s/epoch'.format(info.epoch, rate)
            last_epoch = info.epoch
            last_time = info.time
            score = assess_prediction_functions(dataset, functions=predict_fcn, costs=score_measure, print_results=True)
            p = InfoScorePair(info, score)
            info_score_pairs.append(p)
            # print p.get_table(remove_headers=len(info_score_pairs)>1)
            if test_callback is not None:
                test_callback(info, score)
        if not info.done:
            train_fcn(x_mini, y_mini)
            if training_callback is not None:
                training_callback(info, x_mini, y_mini)
    return info_score_pairs


def get_best_score(score_info_pairs, subset = 'test', prediction_function = None, score_measure = None, lower_is_better = False):
    """
    DEPRECATED!!!

    Given a list of (info, score) pairs which represet the progress over training, find the best score and return it.
    :param score_info_pairs: A list<(IterationInfo, dict)> of the type returned in train_and_test_online_predictor
    :param subset: 'train' or 'test' ... which subset to use to look for the best score
    :param prediction_function: Which prediction function (if there are multiple prediction functions, otherwise leave blank)
    :param score_measure: Which score measure (if there are multiple score measures, otherwise leave blank)
    :param lower_is_better: True if a lower score is better for the chosen score_measure
    :return: best_info, best_score
        best_info is an InterationInfo object
        best_score is a dict<(subset, prediction_function, score_measure) -> score>
    """
    assert len(score_info_pairs)>0, "You need to have at least one score to determine the best one."
    _, first_score = score_info_pairs[0]
    all_subsets, all_functions, all_measures = [remove_duplicates(s) for s in zip(*first_score.keys())]
    if prediction_function is None:
        assert len(all_functions)==1, "You did not specify prediction_function... options are: {}".format(all_functions)
        prediction_function = all_functions[0]
    if score_measure is None:
        assert len(all_measures)==1, "You did not specify a score_measure... options are: {}".format(all_measures)
        score_measure = all_measures[0]
    best_info = None
    best_score = None
    for info, score in score_info_pairs:
        this_is_the_best = best_score is None or \
            (score[subset, prediction_function, score_measure]<best_score[subset, prediction_function, score_measure]) == lower_is_better
        if this_is_the_best:
            best_score = score
            best_info = info
    return best_info, best_score


def print_best_score(score_info_pairs, **best_score_kwargs):
    # DEPRECATED!!!
    best_info, best_score = get_best_score(score_info_pairs, **best_score_kwargs)
    print_score_results(score=best_score, info=best_info)
