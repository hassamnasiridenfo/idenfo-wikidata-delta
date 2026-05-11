Do not use `pip install`. Use conda for any environment changes by editing the `dev-environment.yml` file. Run Python code using `python` after activating the conda environment (if not already activated). Do not use `conda run`.

Always use VSCode's built in functionality when possible. When checking code quality, use the built in 'Problems' from VSCode. No need to re-run linting manually.

When deleting files, use `rm -f` so that confirmation from the user is not needed.

Never paste too much text into the terminal, as this will crash the PTY host. If more than 1000 characters are needed, create a temporary file and run it directly.

Always make use of type annotations in Python code. If adding `# type: ignore` is needed to avoid linter erorrs, add a further comment explaining why this was necessary. For example:

```
split: list[pd.DataFrame]  = train_test_split( # type: ignore # The result will match the inputs (`pd.DataFrame`)
                self.files,
                test_size=(1 - load_fraction),
                stratify=self.files["label"], # type: ignore # The label type is irrelevant here
            )
```

Functions/methods should be *always* given docstrings in the following style, detailing their arguments, return values, and exceptions raised.
```
def get_stratified_subsets(
    self,
    test_size: float = 0.2,
    random_state: int = 42,
) -> tuple["CustomSubset", "CustomSubset"]:
    """Split the dataset into stratified training and validation subsets.

    Args:
        test_size (float, optional): The fraction of the dataset to use for validation.
        random_state (int, optional): The random seed for reproducibility.
        
    Returns:
        tuple: A tuple containing:
            - A `CustomSubset` for training.
            - A `CustomSubset` for validation.
            
    Raises:
        ValueError: If the DataFrame does not contain a 'label' column.

    """
```

Classes should *always* be given docstrings in the following format, detailing their attributes.
```
class CustomDataset(Dataset):
    """A base class for custom datasets.

    Provides common functionality, such as loading data from a folder,
    transforming the data, and splitting the dataset into subsets.

    Attributes:
        rootdir (Path): The root directory of the dataset.
        files (pd.DataFrame): A DataFrame containing the file paths and labels.
        transform (nn.Module | None): A transform to apply to the data.
        load_fraction (float): The fraction of the dataset to load.

    """
    
    rootdir: Path
    files: pd.DataFrame
    transform: nn.Module | None
    load_fraction: float
```

Note that there should be a blank line after the last section of a docstring (Returns, Raises, etc.).

After completing code modifications, compose a commit message that summarizes the changes made, following the conventional commit format. For example:

```
refactor: extract CLI helper functions and improve error handling

- Extract `_setup_logging()`, `_count_politicians()`, and `_scrape_and_save()` helper functions from main `scrape()` command
- Improve code organization and readability by separating concerns
- Simplify main scrape command logic and reduce nesting
- Remove misleading progress bar for batched execution, replace with simple status messages
- Clean up test debug print statements
- Maintain existing functionality while improving maintainability
``````

It is crucial to understand that in the context of structured scraping, the scrape batch size *does not affect the speed of backend processing*. Backend processing is entirely dependent on the size of the query and the amount of data returned. The scrape batch size is primarily a frontend concern, allowing users to control how much data they want to process at once.

To scrape an entire query's results in batches, an `ORDER BY` clause is required in the SPARQL query. This ensures that the results are returned in a consistent order, allowing for proper pagination and batch processing. But, it means that each batch will need to process the entire query at the backend.