# Liber3: An Open Sourced Decentralized eBook Search Engine


Introducing Liber3, a tool for searching ebooks stored on [IPFS](https://ipfs.tech/). It's based on a decentralized data protocol - [Glitter Protocol](https://twitter.com/GlitterProtocol).

You could use Liber3 to search for IPFS links base on file names and displays search results with a simple interface.

There is also [a web version of Liber3](https://liber3.eth.limo) works on [ENS](https://ens.domains/) and [IPFS](https://ipfs.tech/) available if you do not have Python environment.

## Getting Started

To get started, please follow these steps:

### Prerequisites

- Python (v3.7 or higher)

### Installation

Installing the tool, and you should make sure `your/download/path` in the `$PATH`, then you can use the command line tool.

```shell
pip install lib3
``` 

### Options

- `terms`:Specifies search terms to be queried. Required:yes.

- `-p <page>` or `--page <page>`:Specifies the page of results to display. Default: 0.

- `-l <limit>` or `--limit <limit>`:Specifies the number of per page to display. Default: 10.

- `-t <filter type>` or `--type <fliter type>`:Specifies the book extension of result to display. Default: all.
  - `epub` :epub extension.
  - `pdf`:pdf extension.
  - `mobi` :mobi extension.
  - `azw3` :azw3 extension.
  - `djvu` :djvu extension.

### Examples

1. Search for keyword "algebra":

```shell
lib3 algebra
```

2. Search for keywords "linear algebra" and page 1, limit 5:

```shell
lib3 "linear algebra" -p 1 -l 5 
```

3. Search for keywords "linear algebra" and only keep the pdf resource:

```shell
lib3 "linear algebra" -t pdf
```

## Built With

- [glitter-sdk-py](https://github.com/glitternetwork/glitter-sdk-py) A Python SDK for interacting with the Glitter Protocol.

## Contributing

If you would like to contribute to this project, feel free to fork the repository and submit a pull request with your changes.

## License

This project is licensed under the MIT License - see the LICENSE file for details.

