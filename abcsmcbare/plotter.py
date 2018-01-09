import matplotlib.pyplot as plt
import numpy as np
from .PriorType import PriorType
from matplotlib.ticker import FormatStrFormatter


def bin_data(d, w, nbins):
    d_max = np.max(d)
    d_min = np.min(d) - 1e-6  # ensures that the lowest entry is included in the first bin
    bin_width = (d_max - d_min) / nbins

    bin_l = np.array([d_min + i * bin_width for i in range(nbins)])
    bin_u = np.array([d_min + (i + 1) * bin_width for i in range(nbins)])
    bin_c = np.array([bin_l[i] + bin_width / 2 for i in range(nbins)])

    count = np.zeros([nbins])

    for k in range(len(d)):
        kd = d[k]
        kw = w[k]

        for i in range(nbins):
            if bin_l[i] < kd <= bin_u[i]:
                count[i] = count[i] + kw
                break

    return [bin_c, count]


def acceptanceRatioAndEpsilonByPopulation(allResults):
    rates = [x.rate for x in allResults]
    epsilons            = [r.epsilon for r in allResults]

    plt.plot(rates, '--', linewidth=2, label='Acceptance Rate')

    ax1 = plt.gca()
    ax2 = ax1.twinx()

    ax2.plot(epsilons, '-', label='Tolerance', linewidth=2)

    ax1.legend(['Population Acceptance Rate'], loc=2)
    ax2.legend(['Population Tolerance', ], loc=1)
    ax1.set_xlabel('Population')
    ax1.set_ylabel('Acceptance Ratio')
    ax2.set_ylabel('Tolerance')


def modelMarginsByPopulation(allResults, models):
    marginsByPopulation = [r.margins for r in allResults]
    epsilons            = [r.epsilon for r in allResults]
    plt.plot(marginsByPopulation, 'o-', linewidth=2)

    ax1 = plt.gca()
    ax2 = ax1.twinx()

    ax2.plot(epsilons, '--', label='Tolerance')

    ax1.legend([m.name + ' model marginal' for m in models], loc=2)
    ax2.legend(['Population Tolerance', ], loc=1)
    plt.xlabel('Population')
    ax1.set_ylabel('Model margin')
    ax2.set_ylabel('Tolerance')
    ax1.set_xlabel('Population')

def plotHistogram(result, modelIndex, parameterIndexes=None, models=None, bins=9):
    if parameterIndexes is None:
        parameterIndexes = nonConstantParameterIndexes(models[modelIndex])

    np = len(parameterIndexes)
    if np == 1:
        sq = (1, 1)
    elif np == 2:
        sq = (2, 1)
    elif np == 3:
        sq = (3, 1)
    elif np == 4:
        sq = (2, 2)
    elif np == 5 or np == 6:
        sq = (3, 2)
    else:
        tmp = np.ceil(np ** 0.5)
        sq = (int(tmp), int(np.ceil(np.np/tmp)))

    fs = (4*sq[0], 4*sq[1])
    fig, (axs) = plt.subplots(ncols=sq[0], nrows=sq[1], figsize=fs)
    axs = axs.flatten()
    for i, parameterIndex in enumerate(parameterIndexes):
        thisParams = result.parameters[result.models == modelIndex]
        x = [y[parameterIndex] for y in thisParams]
        w = result.weights[result.models == modelIndex]
        histogram_x, histogram_y = bin_data(x, w, int(bins))

        max_x = max(histogram_x)
        min_x = min(histogram_x)
        range_x = max_x - min_x

        if models:
            label = models[modelIndex].parameterNames[parameterIndex]
        else:
            label = 'parameter ' + repr(parameterIndex)

        axs[i].bar(histogram_x, histogram_y, color='#0059b3', width=range_x / bins, align='center', alpha=.5, label=label)

def nonConstantParameterIndexes(model):
    pi = []
    for index, pt in enumerate(model.prior):
        if pt.type is not PriorType.constant:
            pi.append(int(index))

    return pi


def doPairPlot(allResults, modelIndex, populationsIndex, models, actualValues=None,actualValuesColor='yellow',plotHistogramOnFullRange=False):
    """Do a pair plot, max dim 20.

    actualValues must include the constant elements too (it didnt used to)
    """
    parametersForModelByPopulation = [r.parameters[r.models == modelIndex] for r in allResults]
    weightsForModelByPopulation    = [r.weights[r.models == modelIndex] for r in allResults]
    model                          = models[modelIndex]

    nonConstantPIs = nonConstantParameterIndexes(models[modelIndex])
    dim         = len(nonConstantPIs)

    if dim < 5:
        actualValuesLineWidth = 4
    else:
        actualValuesLineWidth = 2

    my_colors = ['#000000', '#003399', '#3333FF', '#6666FF', '#990000', '#CC0033', '#FF6600', '#FFCC00', '#FFFF33',
                 '#33CC00', '#339900', '#336600']

    if len(populationsIndex) > len(my_colors):
        q = int(np.ceil(len(populationsIndex) / len(my_colors)))

        for slopes in range(q):
            my_colors.extend(my_colors)

    max1 = 20.0

    fig, (axs) = plt.subplots(ncols=dim, nrows=dim, figsize=(16, 16))

    assert dim <= max1, NotImplementedError('I am afraid only allowing 20 non-constant dimensions for now!')

    maxValueByPI = [-np.inf for x in range(dim)]
    minValueByPI = [+np.inf for x in range(dim)]

    permutation = np.zeros([dim ** 2, 2])
    k = 0
    for i in range(1, dim + 1):
        for counter, populationIndex in enumerate(populationsIndex):
            thisValues = [tmp[nonConstantPIs[int(i-1)]] for tmp in parametersForModelByPopulation[populationIndex]]
            maxValueByPI[i-1]=np.max((np.max(thisValues),maxValueByPI[i-1]))
            minValueByPI[i-1]=np.min((np.min(thisValues),minValueByPI[i-1]))  

        for j in range(1, dim + 1):
            permutation[k][0] = i
            permutation[k][1] = j
            k += 1

    bin_b = 20.0
    i2 = 0
    for i in range(len(permutation)):
        plt.subplot(dim, dim, i + 1)
        w = weightsForModelByPopulation[populationsIndex[-1]]
        for counter, populationIndex in enumerate(populationsIndex):
            x = [tmp[nonConstantPIs[int(permutation[i][0]-1)]] for tmp in parametersForModelByPopulation[populationIndex]]
            y = [tmp[nonConstantPIs[int(permutation[i][1]-1)]] for tmp in parametersForModelByPopulation[populationIndex]]

            if i % dim == 0:
                plt.ylabel(model.parameterNames[nonConstantPIs[int(permutation[i][0])-1]])
            if i < dim:
                plt.title(model.parameterNames[nonConstantPIs[int(permutation[i][1])-1]])
            if permutation[i][0] == permutation[i][1]:
                if populationIndex == populationsIndex[-1]:
                    plt.cla()
                    if i == 0:
                        plt.ylabel(model.parameterNames[nonConstantPIs[int(permutation[i][0])-1]])
                        plt.title(model.parameterNames[nonConstantPIs[int(permutation[i][1])-1]])
                    if not (len(x) == 0):
                        i2 += 1
                        histogram_x, histogram_y = bin_data(x, w, int(bin_b))

                        max_x = max(histogram_x)
                        min_x = min(histogram_x)
                        range_x = max_x - min_x
                        plt.bar(histogram_x, histogram_y, width=range_x / bin_b, color=my_colors[counter], align='center', alpha=0.5)
                        # plt.title(model.parameterNames[nonConstantPIs[int(permutation[i][0])-1]])
                        if actualValues is not None:
                            plt.vlines(actualValues[nonConstantPIs[int(permutation[i][0])-1]], 0, plt.gca().get_ylim()[1], linewidth=actualValuesLineWidth, colors=actualValuesColor, linestyles='--', label='')

                        if plotHistogramOnFullRange:
                            plt.xlim([minValueByPI[int(permutation[i][0]-1)],maxValueByPI[int(permutation[i][0]-1)]])

            else:
                if not (len(x) == 0):
                    tag = str(populationIndex)
                    plt.scatter(y, x, s=20, marker='o', c=my_colors[counter], edgecolor=my_colors[counter], alpha=0.5, label=tag)

                    if i == len(permutation)-2:
                        plt.legend(loc='lower right', bbox_to_anchor=(1.5, -0.8), fancybox=True, shadow=False, ncol=5, prop={'size': 18})

                    if actualValues is not None and populationIndex == populationsIndex[-1]:
                        plt.scatter([actualValues[nonConstantPIs[int(permutation[i][1]-1)]]], [actualValues[nonConstantPIs[int(permutation[i][0]-1)]]], marker='+', s=5000, color=actualValuesColor, linewidth=actualValuesLineWidth)

            
                if plotHistogramOnFullRange:
                    plt.ylim([minValueByPI[int(permutation[i][0]-1)],maxValueByPI[int(permutation[i][0]-1)]])
                    plt.xlim([minValueByPI[int(permutation[i][1]-1)],maxValueByPI[int(permutation[i][1]-1)]])

            xmin, xmax = plt.xlim()
            ymin, ymax = plt.ylim()

            if not plotHistogramOnFullRange:
                plt.axis([xmin, xmax, ymin, ymax])
            if True:            
                plt.xticks((xmin, (xmin + xmax) / 2.0, xmax), size='xx-small')
                plt.yticks((ymin, (ymin + ymax) / 2.0, ymax), size='xx-small')
                ax = plt.gca()
                ax.xaxis.set_major_formatter(FormatStrFormatter('%.1f'))
                ax.yaxis.set_major_formatter(FormatStrFormatter('%.1f'))
            else:
                plt.xticks([])
                plt.yticks([])

    if False:
        fig.suptitle(model.name)
