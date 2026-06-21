# Implementation Guide: Building Basic Neural Networks with PyTorch & TensorFlow Examples

## Table of Contents
1. [Introduction](#introduction)
2. [Prerequisites](#prerequisites)
3. [PyTorch Implementation Examples](#pytorch-implementation-examples)
   - 3.1 [Building a Simple Linear Regression Network](#building-a-simple-linear-regression-network)
   - 3.2 [Building a Multi-Layer Perceptron (MLP)](#building-a-multi-layer-perceptron-mlp)
   - 3.3 [Convolutional Neural Network (CNN) for Images](#convolutional-neural-network-cnn-for-images)
4. [TensorFlow/Keras Implementation Examples](#tensorflowkeras-implementation-examples)
   - 4.1 [Building a Simple Linear Regression Model](#building-a-simple-linear-regression-model)
   - 4.2 [Building a Multi-Layer Perceptron (MLP)](#building-a-multi-layer-perceptron-mlp-tensorflow)
   - 4.3 [Convolutional Neural Network (CNN) for Images](#convolutional-neural-network-cnn-for-images-tensorflow)
5. [Training & Evaluation Best Practices](#training--evaluation-best-practices)
6. [Common Pitfalls and Solutions](#common-pitfalls-and-solutions)

---

## Introduction

This guide provides practical, hands-on examples for building basic neural networks using **PyTorch** and **TensorFlow/Keras**. These implementations cover the fundamental concepts of neural network architecture and training.

### Why Learn from Scratch?

Building neural networks from scratch (even with high-level APIs) helps you understand:
- How data flows through layers
- The role of activation functions
- Weight initialization strategies
- Training dynamics
- Model evaluation techniques

---

## Prerequisites

Before diving into examples, ensure you have:

### Python Environment (PyTorch or TensorFlow)

```bash
# Install PyTorch
pip install torch torchvision torchaudio

# Or install TensorFlow
pip install tensorflow

# For visualization (optional but recommended)
pip install matplotlib seaborn
```

### Key Concepts Review

| Concept | Description |
|---------|-------------|
| **Tensor** | Multi-dimensional array for data storage and computation |
| **Layer** | A transformation applied to input data (e.g., linear, convolutional) |
| **Activation Function** | Non-linear function that introduces complexity (ReLU, Sigmoid, etc.) |
| **Loss Function** | Measures how wrong predictions are (MSE, CrossEntropy) |
| **Optimizer** | Algorithm for updating weights to minimize loss (SGD, Adam) |

---

## PyTorch Implementation Examples

### 3.1 Building a Simple Linear Regression Network

```python
import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import DataLoader, TensorDataset

# ============================================
# Step 1: Data Preparation
# ============================================

# Generate synthetic data for linear regression (y = 2x + 3)
X = torch.randn(1000, 1)          # Input features
noise = torch.randn(1000, 1) * 0.1  # Add noise
y = 2 * X + 3 + noise             # Target values

# Create dataset and dataloader
dataset = TensorDataset(X, y)
train_dataset, test_dataset = torch.utils.data.random_split(dataset, [800, 200])
train_loader = DataLoader(train_dataset, batch_size=64, shuffle=True)
test_loader = DataLoader(test_dataset, batch_size=32, shuffle=False)

# ============================================
# Step 2: Define the Neural Network Model
# ============================================

class LinearRegressionNet(nn.Module):
    """Simple linear regression neural network"""
    
    def __init__(self, input_dim=1, hidden_dim=32):
        super(LinearRegressionNet, self).__init__()
        
        # Define layers: Input -> Hidden (ReLU) -> Output
        self.network = nn.Sequential(
            nn.Linear(input_dim, hidden_dim),  # First linear layer
            nn.ReLU(),                         # Activation function
            nn.Linear(hidden_dim, 1)           # Output layer
        )
    
    def forward(self, x):
        return self.network(x)

# Initialize model
model = LinearRegressionNet(input_dim=1, hidden_dim=32)

# ============================================
# Step 3: Loss Function and Optimizer
# ============================================

criterion = nn.MSELoss()  # Mean Squared Error for regression
optimizer = optim.Adam(model.parameters(), lr=0.001)  # Adam optimizer

# ============================================
# Step 4: Training Loop
# ============================================

num_epochs = 100
model.train()

for epoch in range(num_epochs):
    total_loss = 0
    
    for batch_x, batch_y in train_loader:
        # Forward pass (prediction)
        predictions = model(batch_x)
        
        # Calculate loss
        loss = criterion(predictions, batch_y)
        
        # Backward pass (backpropagation)
        optimizer.zero_grad()  # Clear gradients from previous iteration
        loss.backward()       # Compute gradients
        
        # Update weights
        optimizer.step()
        
        total_loss += loss.item()
    
    # Print progress every 10 epochs
    if (epoch + 1) % 10 == 0:
        avg_loss = total_loss / len(train_loader)
        print(f"Epoch [{epoch+1}/{num_epochs}], Loss: {avg_loss:.4f}")

# ============================================
# Step 5: Evaluation on Test Data
# ============================================

model.eval()
with torch.no_grad():
    test_predictions = model(test_dataset.tensors[0])
    test_loss = criterion(test_predictions, test_dataset.tensors[1]).item()
    
print(f"Test Loss: {test_loss:.4f}")

# Visualize predictions vs actual values
import matplotlib.pyplot as plt
plt.scatter(test_dataset.tensors[0].numpy(), 
            (2 * test_dataset.tensors[0] + 3).numpy(), label='Actual')
plt.scatter(test_dataset.tensors[0].numpy(), 
            test_predictions.numpy().flatten(), label='Predicted', c='red')
plt.xlabel('Input X')
plt.ylabel('Output Y')
plt.legend()
plt.title("Linear Regression Neural Network Results")
plt.show()
```

### 3.2 Building a Multi-Layer Perceptron (MLP) for Classification

```python
import torch
import torch.nn as nn
import torch.optim as optim
from sklearn.datasets import make_classification
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import accuracy_score, classification_report

# ============================================
# Step 1: Data Preparation (MNIST-like synthetic dataset)
# ============================================

X, y = make_classification(n_samples=2000, n_features=8, 
                           n_informative=6, n_redundant=2,
                           n_clusters_per_class=1, random_state=42)

# Split into train and test sets
X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

# Standardize features (important for neural networks!)
scaler = StandardScaler()
X_train_scaled = scaler.fit_transform(X_train)
X_test_scaled = scaler.transform(X_test)

# Convert to PyTorch tensors and create dataloaders
train_dataset = TensorDataset(torch.FloatTensor(X_train_scaled), 
                              torch.LongTensor(y_train))
test_dataset = TensorDataset(torch.FloatTensor(X_test_scaled), 
                             torch.LongTensor(y_test))

train_loader = DataLoader(train_dataset, batch_size=64, shuffle=True)
test_loader = DataLoader(test_dataset, batch_size=32, shuffle=False)

# ============================================
# Step 2: Define the MLP Model for Classification
# ============================================

class MLPClassifier(nn.Module):
    """Multi-Layer Perceptron for classification tasks"""
    
    def __init__(self, input_dim, hidden_dims=[64, 32], num_classes=10, dropout_rate=0.2):
        super(MLPClassifier, self).__init__()
        
        # Build the network layer by layer
        layers = []
        current_dim = input_dim
        
        for hidden_dim in hidden_dims:
            layers.append(nn.Linear(current_dim, hidden_dim))
            layers.append(nn.ReLU())      # Activation function
            layers.append(nn.Dropout(dropout_rate))  # Prevent overfitting
            current_dim = hidden_dim
        
        layers.append(nn.Linear(current_dim, num_classes))  # Output layer
        self.network = nn.Sequential(*layers)
    
    def forward(self, x):
        return self.network(x)

# Initialize model
input_dim = X_train.shape[1]
model = MLPClassifier(input_dim=input_dim, hidden_dims=[64, 32], 
                      num_classes=2, dropout_rate=0.2)

# ============================================
# Step 3: Loss Function and Optimizer for Classification
# ============================================

criterion = nn.CrossEntropyLoss()  # Cross-entropy loss for classification
optimizer = optim.Adam(model.parameters(), lr=0.001)
scheduler = optim.lr_scheduler.StepLR(optimizer, step_size=50, gamma=0.5)

# ============================================
# Step 4: Training Loop with Early Stopping Check
# ============================================

num_epochs = 200
best_accuracy = 0
patience = 20
no_improve_count = 0

model.train()
for epoch in range(num_epochs):
    total_loss = 0
    correct = 0
    total = 0
    
    for batch_x, batch_y in train_loader:
        # Forward pass
        predictions = model(batch_x)
        
        # Calculate loss
        loss = criterion(predictions, batch_y.long())
        
        # Backward pass and update weights
        optimizer.zero_grad()
        loss.backward()
        optimizer.step()
        
        total_loss += loss.item()
        _, predicted = torch.max(predictions.data, 1)
        total += batch_y.size(0)
        correct += (predicted == batch_y).sum().item()
    
    # Calculate metrics
    accuracy = correct / total
    avg_loss = total_loss / len(train_loader)
    
    if (epoch + 1) % 20 == 0:
        print(f"Epoch [{epoch+1}/{num_epochs}], Loss: {avg_loss:.4f}, "
              f"Accuracy: {accuracy*100:.2f}%")
    
    # Learning rate scheduling
    scheduler.step()

# ============================================
# Step 5: Evaluation on Test Data
# ============================================

model.eval()
with torch.no_grad():
    test_predictions = model(X_test_scaled)
    _, predicted = torch.max(test_predictions.data, 1)
    
test_accuracy = (predicted == y_test).float().mean().item() * 100

print(f"\nTest Accuracy: {test_accuracy:.2f}%")
print(classification_report(y_test, predicted))
```

### 3.3 Convolutional Neural Network (CNN) for Images

```python
import torch
import torch.nn as nn
import torch.optim as optim
from torchvision import datasets, transforms
from torch.utils.data import DataLoader

# ============================================
# Step 1: Data Preparation with Image Dataset
# ============================================

# Define data transformations
transform = transforms.Compose([
    transforms.RandomCrop(32, padding=4),      # Random cropping for augmentation
    transforms.RandomHorizontalFlip(),         # Horizontal flip augmentation
    transforms.ToTensor(),                     # Convert to tensor
    transforms.Normalize((0.5, 0.5, 0.5), (0.5, 0.5, 0.5))  # Normalize
])

# Load dataset (using CIFAR-10 as example)
train_dataset = datasets.CIFAR10(root='./data', train=True, 
                                  download=True, transform=transform)
test_dataset = datasets.CIFAR10(root='./data', train=False,
                                download=True, transform=transforms.Compose([
                                    transforms.ToTensor(),
                                    transforms.Normalize((0.5, 0.5, 0.5), (0.5, 0.5, 0.5))
                                ]))

train_loader = DataLoader(train_dataset, batch_size=64, shuffle=True)
test_loader = DataLoader(test_dataset, batch_size=100, shuffle=False)

# ============================================
# Step 2: Define CNN Architecture
# ============================================

class SimpleCNN(nn.Module):
    """Simple Convolutional Neural Network for image classification"""
    
    def __init__(self, num_classes=10):
        super(SimpleCNN, self).__init__()
        
        # Convolutional layers
        self.conv_layers = nn.Sequential(
            # First convolution block
            nn.Conv2d(in_channels=3, out_channels=32, kernel_size=3, padding=1),  # 3 -> 32 channels
            nn.BatchNorm2d(32),          # Batch normalization for stability
            nn.ReLU(),                   # Activation function
            nn.MaxPool2d(kernel_size=2, stride=2),  # Downsample
            
            # Second convolution block
            nn.Conv2d(in_channels=32, out_channels=64, kernel_size=3, padding=1),
            nn.BatchNorm2d(64),
            nn.ReLU(),
            nn.MaxPool2d(kernel_size=2, stride=2)  # Downsample
        )
        
        # Fully connected layers
        self.fc_layers = nn.Sequential(
            nn.Flatten(),                # Flatten spatial dimensions
            nn.Linear(64 * 8 * 8, 128),  # Last feature map size: 32 -> 64 after pooling
            nn.ReLU(),
            nn.Dropout(0.5),             # Dropout for regularization
            nn.Linear(128, num_classes)  # Output layer
        )
    
    def forward(self, x):
        x = self.conv_layers(x)
        x = self.fc_layers(x)
        return x

# Initialize model
model = SimpleCNN(num_classes=10)

# ============================================
# Step 3: Loss Function and Optimizer
# ============================================

criterion = nn.CrossEntropyLoss()
optimizer = optim.Adam(model.parameters(), lr=0.001, weight_decay=1e-4)
scheduler = optim.lr_scheduler.StepLR(optimizer, step_size=50, gamma=0.1)

# ============================================
# Step 4: Training Loop with Validation
# ============================================

num_epochs = 20
best_accuracy = 0
patience = 5
no_improve_count = 0

model.train()
for epoch in range(num_epochs):
    # Training phase
    model.train()
    train_loss = 0
    correct = 0
    
    for batch_x, batch_y in train_loader:
        predictions = model(batch_x)
        loss = criterion(predictions, batch_y)
        
        optimizer.zero_grad()
        loss.backward()
        optimizer.step()
        
        train_loss += loss.item()
        _, predicted = torch.max(predictions.data, 1)
        correct += (predicted == batch_y).sum().item()
    
    # Validation phase
    model.eval()
    with torch.no_grad():
        test_predictions = model(test_loader.dataset.test_images)
        test_loss = criterion(test_predictions, test_loader.dataset.targets)
        _, predicted = torch.max(test_predictions.data, 1)
        accuracy = (predicted == test_loader.dataset.targets).float().mean().item() * 100
    
    if (epoch + 1) % 5 == 0:
        avg_train_loss = train_loss / len(train_loader)
        print(f"Epoch [{epoch+1}/{num_epochs}], "
              f"Train Loss: {avg_train_loss:.4f}, "
              f"Test Accuracy: {accuracy:.2f}%")
    
    scheduler.step()

# ============================================
# Step 5: Final Evaluation and Model Saving
# ============================================

model.eval()
with torch.no_grad():
    test_predictions = model(test_loader.dataset.test_images)
    _, predicted = torch.max(test_predictions.data, 1)
    
test_accuracy = (predicted == test_loader.dataset.targets).float().mean().item() * 100
print(f"\nFinal Test Accuracy: {test_accuracy:.2f}%")

# Save the model
torch.save(model.state_dict(), 'cifar10_cnn_model.pth')
print("Model saved successfully!")
```

---

## TensorFlow/Keras Implementation Examples

### 4.1 Building a Simple Linear Regression Model

```python
import tensorflow as tf
from sklearn.datasets import make_regression
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler
import numpy as np

# ============================================
# Step 1: Data Preparation
# ============================================

# Generate synthetic data (y = 2x + 3)
X, y = make_regression(n_samples=1000, n_features=1, noise=0.1, random_state=42)

# Split into train and test sets
X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

# Standardize features
scaler_x = StandardScaler()
y_scaler = StandardScaler()
X_train_scaled = scaler_x.fit_transform(X_train)
X_test_scaled = scaler_x.transform(X_test)
y_train_scaled = y_scaler.fit_transform(y_train.reshape(-1, 1))
y_test_scaled = y_scaler.transform(y_test.reshape(-1, 1))

# Convert to TensorFlow datasets
train_dataset = tf.data.Dataset.from_tensor_slices((X_train_scaled, y_train_scaled))
test_dataset = tf.data.Dataset.from_tensor_slices((X_test_scaled, y_test_scaled))

train_dataset = train_dataset.batch(32).shuffle(1000).prefetch(tf.data.AUTOTUNE)
test_dataset = test_dataset.batch(32).prefetch(tf.data.AUTOTUNE)

# ============================================
# Step 2: Define the Model using Functional API
# ============================================

model = tf.keras.Sequential([
    tf.keras.layers.Input(shape=(1,)),              # Input layer
    tf.keras.layers.Dense(32, activation='relu'),   # Hidden layer with ReLU
    tf.keras.layers.Dense(1)                        # Output layer (no activation for regression)
])

# ============================================
# Step 3: Compile the Model
# ============================================

model.compile(
    optimizer=tf.keras.optimizers.Adam(learning_rate=0.001),
    loss='mean_squared_error',                      # Loss function for regression
    metrics=['mae']                                 # Mean Absolute Error metric
)

print(model.summary())  # Print model architecture

# ============================================
# Step 4: Train the Model
# ============================================

history = model.fit(
    train_dataset,
    epochs=100,
    validation_split=0.1,
    verbose=1,
    callbacks=[
        tf.keras.callbacks.EarlyStopping(patience=20, restore_best_weights=True),  # Stop if no improvement
        tf.keras.callbacks.ReduceLROnPlateau(factor=0.5, patience=10)  # Reduce LR if loss plateaus
    ]
)

# ============================================
# Step 5: Evaluate on Test Data
# ============================================

test_loss, test_mae = model.evaluate(test_dataset, verbose=0)
print(f"\nTest Loss (MSE): {test_loss:.4f}")
print(f"Test MAE: {test_mae:.4f}")

# Make predictions and convert back to original scale
y_pred_scaled = model.predict(X_test_scaled)[:, 0]
y_pred = y_scaler.inverse_transform(y_pred_scaled.reshape(-1, 1)).flatten()
y_true = y_test.flatten()

# Visualize results
import matplotlib.pyplot as plt
plt.scatter(y_true, y_pred, alpha=0.5)
plt.plot([min(y_true), max(y_true)], [min(y_true), max(y_true)], 'r--')
plt.xlabel('Actual Values')
plt.ylabel('Predicted Values')
plt.title("Linear Regression Model Results")
plt.show()

# Save the model
model.save('linear_regression_model.h5')
print("\nModel saved successfully!")
```

### 4.2 Building a Multi-Layer Perceptron (MLP) for Classification

```python
import tensorflow as tf
from sklearn.datasets import make_classification
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import accuracy_score, classification_report
import numpy as np

# ============================================
# Step 1: Data Preparation
# ============================================

X, y = make_classification(n_samples=2000, n_features=8, 
                           n_informative=6, random_state=42)

X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

# Standardize features
scaler = StandardScaler()
X_train_scaled = scaler.fit_transform(X_train)
X_test_scaled = scaler.transform(X_test)

# Convert to TensorFlow datasets
train_dataset = tf.data.Dataset.from_tensor_slices((X_train_scaled, y_train))
test_dataset = tf.data.Dataset.from_tensor_slices((X_test_scaled, y_test))

train_dataset = train_dataset.batch(64).shuffle(1000).prefetch(tf.data.AUTOTUNE)
test_dataset = test_dataset.batch(32).prefetch(tf.data.AUTOTUNE)

# ============================================
# Step 2: Define the MLP Model with Custom Architecture
# ============================================

def create_mlp(input_dim, hidden_dims=[64, 32], dropout_rate=0.2):
    """Create an MLP model with configurable architecture"""
    
    layers = []
    current_dim = input_dim
    
    # Add hidden layers
    for dim in hidden_dims:
        layers.append(tf.keras.layers.Dense(dim, activation='relu'))
        layers.append(tf.keras.layers.Dropout(dropout_rate))  # Dropout regularization
    
    # Add output layer (no activation for classification with softmax later)
    layers.append(tf.keras.layers.Dense(2))  # Binary classification (2 classes)
    
    return tf.keras.Sequential(layers)

model = create_mlp(input_dim=X_train_scaled.shape[1], 
                   hidden_dims=[64, 32], dropout_rate=0.2)

# ============================================
# Step 3: Compile the Model with Classifiers Loss
# ============================================

model.compile(
    optimizer=tf.keras.optimizers.Adam(learning_rate=0.001),
    loss='sparse_categorical_crossentropy',  # For integer-encoded labels
    metrics=['accuracy']
)

print(model.summary())

# ============================================
# Step 4: Train the Model with Callbacks
# ============================================

model.fit(
    train_dataset,
    epochs=200,
    validation_split=0.1,
    verbose=1,
    callbacks=[
        tf.keras.callbacks.EarlyStopping(patience=30, restore_best_weights=True),
        tf.keras.callbacks.ReduceLROnPlateau(factor=0.5, patience=10)
    ]
)

# ============================================
# Step 5: Evaluate on Test Data
# ============================================

test_loss, test_accuracy = model.evaluate(test_dataset, verbose=0)
print(f"\nTest Loss: {test_loss:.4f}")
print(f"Test Accuracy: {test_accuracy*100:.2f}%")

# Make predictions and generate classification report
y_pred_probs = model.predict(X_test_scaled)
y_pred_classes = np.argmax(y_pred_probs, axis=1)
print(classification_report(y_test, y_pred_classes))

# Save the model
model.save('mlp_classification_model.h5')
print("\nModel saved successfully!")
```

### 4.3 Convolutional Neural Network (CNN) for Images

```python
import tensorflow as tf
from tensorflow.keras.applications import VGG16
from tensorflow.keras.layers import Input, Flatten, Dense, Dropout, BatchNormalization
from tensorflow.keras.models import Model
import numpy as np

# ============================================
# Step 1: Data Preparation with Image Dataset
# ============================================

# Load CIFAR-10 dataset (downloaded automatically)
(x_train, y_train), (x_test, y_test) = tf.keras.datasets.cifar10.load_data()

# Normalize pixel values to [0, 1] range and subtract mean for better training
x_train = x_train.astype('float32') / 255.0 - 0.5
x_test = x_test.astype('float32') / 255.0 - 0.5

# Convert to TensorFlow Dataset format
train_dataset = tf.data.Dataset.from_tensor_slices((x_train, y_train))
test_dataset = tf.data.Dataset.from_tensor_slices((x_test, y_test))

train_dataset = train_dataset.shuffle(1000).batch(64).prefetch(tf.data.AUTOTUNE)
test_dataset = test_dataset.batch(100).prefetch(tf.data.AUTOTUNE)

# ============================================
# Step 2: Define CNN Architecture with Transfer Learning Option
# ============================================

def create_cnn(num_classes=10, use_transfer_learning=False):
    """Create a CNN model for image classification"""
    
    input_shape = (32, 32, 3) if num_classes == 10 else (64, 64, 3)
    
    # Define the base architecture
    inputs = Input(shape=input_shape)
    
    # Convolutional blocks with batch normalization and dropout
    conv_blocks = [
        ('conv_block_1', [32, 3], 'relu', True),      # 3 -> 32 channels, kernel 3x3
        ('conv_block_2', [64, 3], 'relu', True),      # 32 -> 64 channels
        ('conv_block_3', [128, 3], 'relu', True),     # 64 -> 128 channels
    ]
    
    current = inputs
    
    for name, filters, kernel_size, use_bn in conv_blocks:
        current = tf.keras.layers.Conv2D(filters=filters, 
                                         kernel_size=kernel_size, 
                                         padding='same', 
                                         activation=None)(current)  # No activation yet
        
        if use_bn:
            current = BatchNormalization()(current)
        
        current = tf.keras.layers.Activation('relu')(current)
        current = tf.keras.layers.MaxPooling2D(pool_size=(2, 2))(current)
    
    # Fully connected layers
    current = Flatten()(current)
    current = Dense(128, activation='relu')(current)
    current = Dropout(0.5)(current)
    output = Dense(num_classes, activation='softmax')(current)
    
    model = Model(inputs=inputs, outputs=output)
    return model

# Create and compile the model (without transfer learning for simplicity)
model = create_cnn(num_classes=10, use_transfer_learning=False)

print(model.summary())

# ============================================
# Step 3: Compile with Appropriate Loss and Metrics
# ============================================

model.compile(
    optimizer=tf.keras.optimizers.Adam(learning_rate=0.001),
    loss='sparse_categorical_crossentropy',
    metrics=['accuracy']
)

# ============================================
# Step 4: Train the Model with Advanced Callbacks
# ============================================

callbacks = [
    tf.keras.callbacks.EarlyStopping(monitor='val_loss', patience=15, restore_best_weights=True),
    tf.keras.callbacks.ReduceLROnPlateau(factor=0.5, patience=8),
    tf.keras.callbacks.ModelCheckpoint('best_cnn_model.h5', 
                                       save_best_only=True, 
                                       monitor='val_accuracy', 
                                       mode='max')
]

model.fit(
    train_dataset,
    epochs=30,
    verbose=1,
    callbacks=callbacks
)

# ============================================
# Step 5: Evaluate on Test Data
# ============================================

test_loss, test_accuracy = model.evaluate(test_dataset, verbose=0)
print(f"\nTest Loss: {test_loss:.4f}")
print(f"Test Accuracy: {test_accuracy*100:.2f}%")

# Save the best model
model.save('cifar10_cnn_model.h5')
print("\nModel saved successfully!")

# ============================================
# Step 6: Visualize Predictions on Sample Images
# ============================================

import matplotlib.pyplot as plt

def plot_predictions(model, dataset, num_samples=9):
    """Plot predicted classes for sample images"""
    
    x_imgs, y_true = next(iter(dataset))[:num_samples]
    x_imgs = np.array(x_imgs)  # Ensure it's a numpy array
    
    # Get predictions (remove batch dimension)
    preds = model.predict(x_imgs)[0]
    pred_classes = np.argmax(preds, axis=1)
    
    class_names = ['airplane', 'car', 'bird', 'cat', 'deer', 
                   'dog', 'frog', 'horse', 'ship', 'truck']
    
    fig, axes = plt.subplots(3, 3, figsize=(12, 10))
    
    for i, ax in enumerate(axes.flat):
        # Predicted class
        pred_class_idx = pred_classes[i]
        pred_label = class_names[pred_class_idx]
        
        # True label
        true_class_idx = y_true[i]
        true_label = class_names[true_class_idx]
        
        ax.imshow(x_imgs[i])
        title = f"True: {true_label}\nPred: {pred_label}"
        if pred_class_idx == true_class_idx:
            ax.set_title(title, color='green')
        else:
            ax.set_title(title, color='red')
    
    plt.tight_layout()
    plt.show()

plot_predictions(model, test_dataset)
```

---

## Training & Evaluation Best Practices

### 5.1 Data Preprocessing Checklist

| Step | PyTorch Implementation | TensorFlow/Keras Implementation |
|------|------------------------|----------------------------------|
| **Normalization** | `torch.nn.functional.normalize()` or custom scaler | `StandardScaler` for numpy data; built-in normalization for image datasets |
| **One-hot Encoding** | Use `nn.OneHotEmbedding` layer | Built-in in Keras with `CategoricalEncodingLayer` |
| **Padding/Cropping** | Custom padding layers or transforms | `tf.image.pad_to_bounding_box`, `RandomCrop` |

### 5.2 Common Activation Functions Comparison

```python
# PyTorch activation functions
import torch.nn as nn

activations_pytorch = {
    'ReLU': nn.ReLU(),
    'LeakyReLU': nn.LeakyReLU(negative_slope=0.01),
    'Sigmoid': nn.Sigmoid(),
    'Tanh': nn.Tanh(),
    'Softmax': nn.Softmax(dim=-1)  # Note: softmax usually applied at output layer only
}

# TensorFlow/Keras activation functions
import tensorflow as tf

activations_tf = {
    'ReLU': tf.nn.relu,
    'LeakyReLU': tf.nn.leaky_relu,
    'Sigmoid': tf.nn.sigmoid,
    'Tanh': tf.nn.tanh,
    'Softmax': tf.nn.softmax  # Note: use only at the final output layer for classification
}
```

### 5.3 Loss Function Selection Guide

| Task Type | PyTorch Loss | TensorFlow/Keras Loss |
|-----------|--------------|-----------------------|
| **Regression (continuous)** | `nn.MSELoss()` / `nn.L1Loss()` | `'mean_squared_error'` / `'mae'` |
| **Binary Classification** | `nn.BCEWithLogitsLoss()` | `'binary_crossentropy'` |
| **Multi-class Classification** | `nn.CrossEntropyLoss()` | `'categorical_crossentropy'` or `'sparse_categorical_crossentropy'` |
| **Sequence-to-Sequence** | `nn.KLDivLoss()` | `'kullback_leibler_divergence'` |

### 5.4 Key Training Hyperparameters

```python
# Recommended starting values for most use cases:

hyperparameters = {
    'learning_rate': 0.001,           # Adam optimizer default
    'weight_decay': 1e-4,             # L2 regularization (prevent overfitting)
    'dropout_rate': 0.2,              # Dropout ratio for hidden layers
    'batch_size': 64,                 # Balance between memory and gradient stability
    'epochs': 50-200,                 # Depends on dataset complexity
    'early_stopping_patience': 15,    # Stop training if validation loss doesn't improve
}
```

---

## Common Pitfalls and Solutions

### 6.1 Vanishing/Exploding Gradients

| Problem | Symptom | Solution (PyTorch) | Solution (TensorFlow/Keras) |
|---------|---------|---------------------|------------------------------|
| **Vanishing** | Loss decreases very slowly | Use ReLU instead of Sigmoid/Tanh; use BatchNorm; use Xavier/He initialization | Same as PyTorch solutions |
| **Exploding** | Loss becomes NaN/infinite | Apply gradient clipping: `torch.nn.utils.clip_grad_norm_()` | Same as PyTorch solutions |

```python
# Gradient Clipping Example (PyTorch)
for batch_x, batch_y in train_loader:
    predictions = model(batch_x)
    loss = criterion(predictions, batch_y)
    
    optimizer.zero_grad()
    loss.backward()
    
    # Clip gradients to prevent exploding gradients
    torch.nn.utils.clip_grad_norm_(model.parameters(), max_norm=1.0)
    
    optimizer.step()
```

### 6.2 Overfitting Prevention Techniques

| Technique | Implementation Example | When to Use |
|-----------|------------------------|-------------|
| **Dropout** | `nn.Dropout(0.5)` in hidden layers | Always use for deep networks (>2 layers) |
| **Batch Normalization** | `nn.BatchNorm2d()` after conv layers | Essential for training stability |
| **Data Augmentation** | RandomCrop, HorizontalFlip, ColorJitter | For image tasks; helps prevent overfitting |
| **L2 Regularization** | Add to loss: `loss + weight_decay * sum(w^2)` | Use with Adam optimizer (built-in L2) |

### 6.3 Memory Management Best Practices

```python
# Always use 'with torch.no_grad()' during evaluation/inference
model.eval()
with torch.no_grad():
    predictions = model(test_loader.dataset.test_images)

# Free memory after large operations
del batch_x, batch_y, predictions
torch.cuda.empty_cache()  # For GPU users

# Use smaller batches if running out of memory
train_loader = DataLoader(dataset, batch_size=32, shuffle=True)  # Instead of 64 or 128
```

### 6.4 Common Error Messages and Solutions

| Error | Cause | Solution |
|-------|-------|----------|
| `RuntimeError: size mismatch` | Input/output dimension mismatch in layers | Check layer dimensions match expected input shape |
| `CUDA out of memory` | Batch too large for GPU | Reduce batch size or use gradient accumulation |
| `NaN loss` | Gradients exploding or learning rate too high | Reduce learning rate; add gradient clipping |

---

## Summary and Next Steps

### What You've Learned

1. **PyTorch & TensorFlow/Keras** both provide powerful APIs for building neural networks
2. The fundamental components (layers, activation functions, loss, optimizer) are similar across frameworks
3. Best practices like normalization, dropout, and early stopping improve model performance
4. Understanding data preprocessing is crucial before feeding it to the network

### Recommended Learning Path

```
1. ✅ Complete basic linear regression example
2. 📖 Study MLP classification (add Dropout, try different architectures)
3. 🔬 Experiment with CNNs on image datasets (CIFAR-10, MNIST)
4. 💡 Try building a custom dataset loader for your own data
5. 🚀 Move to advanced topics: RNNs/LSTMs, Transformers, Attention mechanisms
```

### Additional Resources

| Resource | Description | Link |
|----------|-------------|------|
| **PyTorch Official Tutorials** | Comprehensive beginner tutorials | [docs.pytorch.org](https://pytorch.org/tutorials/) |
| **TensorFlow/Keras Guide** | Step-by-step ML examples | [tensorflow.org/guide](https://www.tensorflow.org/guide) |
| **Fast.ai Practical Deep Learning** | Learn by doing with practical code | [fast.ai](https://course.fast.ai/) |

---

*Document created: 2026-06-21*  
*Last updated for PyTorch 2.0+ and TensorFlow 2.15+ best practices*