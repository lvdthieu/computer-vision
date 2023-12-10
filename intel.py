import argparse
import random
import time

import matplotlib.pyplot as plt
import numpy as np
import torch
import torch.nn as nn
import torch.optim as optim
import torch.utils.data as data
import torchvision.datasets as datasets
import torchvision.transforms as transforms
from sklearn.metrics import (
    ConfusionMatrixDisplay,
    accuracy_score,
    f1_score,
    precision_score,
    recall_score,
)

from models.alexnet import AlexNet
from models.convnext import ConvNeXt
from models.resnet152 import ResNet152
from models.vgg19 import VGG19

parser = argparse.ArgumentParser()


def plot_images(images, labels, classes, normalize=False):
    n_images = len(images)
    rows = int(np.sqrt(n_images))
    cols = int(np.sqrt(n_images))
    fig = plt.figure(figsize=(10, 10))
    for i in range(rows * cols):
        ax = fig.add_subplot(rows, cols, i + 1)
        image = images[i]
        ax.imshow(image.permute(1, 2, 0).cpu().numpy())
        ax.set_title(classes[labels[i]])
        ax.axis("off")
    plt.show()


def data_augmented(images_folder, image_size=224):
    transform_augument_1 = transforms.Compose(
        [
            transforms.ToTensor(),
            transforms.RandomResizedCrop(size=(image_size, image_size), antialias=True),
            transforms.RandomHorizontalFlip(p=0.5),
            transforms.Normalize((0.5, 0.5, 0.5), (0.5, 0.5, 0.5)),
        ]
    )
    transform_augument_2 = transforms.Compose(
        [
            transforms.ToTensor(),
            transforms.RandomResizedCrop(size=(image_size, image_size), antialias=True),
            transforms.RandomRotation(degrees=(30, 70)),
            transforms.Normalize(mean=[0.5, 0.5, 0.5], std=[0.5, 0.5, 0.5]),
        ]
    )
    data_augument_1 = datasets.ImageFolder(
        images_folder,
        transform=transform_augument_1,
    )
    data_augument_2 = datasets.ImageFolder(
        images_folder,
        transform=transform_augument_2,
    )

    return (data_augument_1) + (data_augument_2)


def initialize_parameters(m):
    """
    Params m: a layer inherit torch.nn.Conv2d or torch.nn.Linear
    """

    if isinstance(m, nn.Conv2d):
        nn.init.kaiming_normal_(m.weight.data, nonlinearity="relu")
        nn.init.constant_(m.bias.data, 0)
    elif isinstance(m, nn.Linear):
        nn.init.xavier_normal_(m.weight.data, gain=nn.init.calculate_gain("relu"))
        nn.init.constant_(m.bias.data, 0)


def calculate_accuracy(y_pred, y):
    top_pred = y_pred.argmax(1, keepdim=True)
    correct = top_pred.eq(y.view_as(top_pred)).sum()
    acc = correct.float() / y.shape[0]
    return acc


def train(model, iterator, optimizer, criterion, device):
    epoch_loss = 0
    epoch_acc = 0
    model.train()
    for x, y in iterator:
        x = x.to(device)
        y = y.to(device)
        optimizer.zero_grad()
        y_pred = model(x)
        loss = criterion(y_pred, y)
        acc = calculate_accuracy(y_pred, y)
        loss.backward()
        optimizer.step()
        epoch_loss += loss.item()
        epoch_acc += acc.item()

    return epoch_loss / len(iterator), epoch_acc / len(iterator)


def evaluate(model, iterator, criterion, device):
    epoch_loss = 0
    epoch_acc = 0

    model.eval()

    with torch.no_grad():
        for x, y in iterator:
            x = x.to(device)
            y = y.to(device)
            y_pred, _ = model(x)
            loss = criterion(y_pred, y)
            acc = calculate_accuracy(y_pred, y)
            epoch_loss += loss.item()
            epoch_acc += acc.item()

    return epoch_loss / len(iterator), epoch_acc / len(iterator)


def epoch_time(start_time, end_time):
    elapsed_time = end_time - start_time
    elapsed_mins = int(elapsed_time / 60)
    elapsed_secs = int(elapsed_time - (elapsed_mins * 60))
    return elapsed_mins, elapsed_secs


def get_result(model, data, device):
    predict = None
    gold = None
    epoch_loss = 0
    epoch_acc = 0

    model.eval()

    with torch.no_grad():
        for x, y in data:
            x = x.to(device)
            y = y.to(device)
            y_pred, _ = model(x)
            top_pred = y_pred.argmax(1, keepdim=True)
            if predict == None:
                predict = top_pred
                gold = y
            else:
                predict = torch.cat([predict, top_pred])
                gold = torch.cat([gold, y])
    predict = predict.cpu()
    gold = gold.cpu()
    precision_macro = precision_score(gold, predict, average="macro")
    recall_macro = recall_score(gold, predict, average="macro")
    f1_macro = f1_score(gold, predict, average="macro")
    accuracy = accuracy_score(gold, predict)
    ConfusionMatrixDisplay.from_predictions(
        gold, predict, display_labels=valid_data.classes, cmap=plt.cm.Blues
    )
    plt.show()
    return {
        "precision macro": precision_macro,
        "recall macro": recall_macro,
        "f1 macro": f1_macro,
        "accuracy": accuracy,
    }


if __name__ == "__main__":
    parser.add_argument(
        "-m",
        "--model",
        dest="model",
        default="alexnet",
        help='Model to experiment (the model must be in ["alexnet", "vgg19", "resnet152", "convnext"])',
    )
    parser.add_argument(
        "-s",
        "--seed",
        dest="seed",
        default=42,
        help="Set seed to have reproduce ability",
        type=int,
    )
    parser.add_argument(
        "-bs",
        "--batch",
        dest="batch_size",
        default=64,
        help="Batch size to train model",
        type=int,
    )
    parser.add_argument(
        "-lr",
        "--learning_rate",
        dest="lr",
        default=1e-4,
        help="Learning rate to train model",
        type=float,
    )
    parser.add_argument(
        "-ep",
        "--epochs",
        dest="epochs",
        default=30,
        help="Number of epochs to train model",
        type=int,
    )

    args = parser.parse_args()
    MODEL = args.model
    SEED = args.seed
    BATCH_SIZE = args.batch_size
    LR = args.lr
    EPOCHS = args.epochs
    if MODEL not in ["alexnet", "vgg19", "resnet152", "convnext"]:
        raise ValueError("Model is not supported")

    random.seed(SEED)
    torch.manual_seed(SEED)
    torch.cuda.manual_seed(SEED)
    torch.backends.cudnn.deterministic = True

    if MODEL == "alexnet":
        image_size = 227
    else:
        image_size = 224

    transform = transforms.Compose(
        [
            transforms.ToTensor(),
            transforms.Normalize((0.5, 0.5, 0.5), (0.5, 0.5, 0.5)),
            transforms.Resize((image_size, image_size)),
        ]
    )
    train_data = datasets.ImageFolder(
        "assets/intel/seg_train/seg_train",
        transform=transform,
    )
    valid_data = datasets.ImageFolder(
        "assets/intel/seg_test/seg_test",
        transform=transform,
    )
    print("Drawing images")
    # Draw some images to have overview of dataset
    N_IMAGES = 25
    images, labels = zip(
        *[(image, label) for image, label in [train_data[i] for i in range(N_IMAGES)]]
    )
    classes = train_data.classes
    plot_images(images, labels, classes)

    # Use data augmented to deal with overfitting
    train_data += data_augmented("assets/intel/seg_train/seg_train", image_size)

    # Load data
    train_iterator = data.DataLoader(
        train_data, shuffle=True, batch_size=BATCH_SIZE, num_workers=2
    )
    valid_iterator = data.DataLoader(
        valid_data, shuffle=True, batch_size=BATCH_SIZE, num_workers=2
    )

    # Define model
    OUTPUT_DIM = 6

    match MODEL:
        case "alexnet":
            model = AlexNet(OUTPUT_DIM)
        case "vgg19":
            model = VGG19(OUTPUT_DIM)
        case "resnet152":
            model = ResNet152(OUTPUT_DIM)
        case "convnext":
            model = ConvNeXt(OUTPUT_DIM)

    model.apply(initialize_parameters)
    optimizer = optim.Adam(model.parameters(), lr=LR)
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    criterion = nn.CrossEntropyLoss()
    model = model.to(device)
    criterion = criterion.to(device)
    best_valid_loss = float("inf")

    print("Training model")
    # Train model
    for epoch in range(EPOCHS):
        start_time = time.time()
        train_loss, train_acc = train(
            model, train_iterator, optimizer, criterion, device
        )
        valid_loss, valid_acc = evaluate(model, valid_iterator, criterion, device)
        if valid_loss < best_valid_loss:
            best_valid_loss = valid_loss
            torch.save(model, "results/model.pt")

        end_time = time.time()

        epoch_mins, epoch_secs = epoch_time(start_time, end_time)

        print(f"Epoch: {epoch+1:02} | Epoch Time: {epoch_mins}m {epoch_secs}s")
        print(f"\tTrain Loss: {train_loss:.3f} | Train Acc: {train_acc*100:.2f}%")
        print(f"\t Val. Loss: {valid_loss:.3f} |  Val. Acc: {valid_acc*100:.2f}%")

    print("Assessing performance")
    # Assess performance
    model_saved = torch.load("results/model.pt")
    get_result(model_saved, valid_iterator, device)
