import React from 'react';
import PropTypes from 'prop-types';

import { Button, Icon } from 'antd';

import ReaderFactory from '../../io/ReaderFactory';
import RawReader from './RawReader';
import style from './FileLoader.mcss';

export default class FileLoader extends React.Component {
  constructor(props) {
    super(props);
    this.state = {
      file: null,
    };

    // Closure for callback
    this.addDataset = this.addDataset.bind(this);
    this.loadFile = this.loadFile.bind(this);
    this.updateReader = this.updateReader.bind(this);
  }

  loadFile() {
    ReaderFactory.openFile(
      ['raw'].concat(ReaderFactory.listSupportedExtensions()),
      (file) => {
        ReaderFactory.loadFile(file).then(
          (reader) => {
            const source = this.props.proxyManager.createProxy(
              'Sources',
              'TrivialProducer',
              { name: file.name }
            );
            source.setInputAlgorithm(reader);
            this.props.proxyManager.createRepresentationInAllViews(source);
            this.props.proxyManager.renderAllViews();
            this.setState({ file: null });
            this.props.updateTab('pipeline');
          },
          () => {
            // No reader found
            this.setState({ file });
          }
        );
      }
    );
  }

  addDataset(ds) {
    if (!ds) {
      this.setState({ file: null });
      return;
    }
    const source = this.props.proxyManager.createProxy(
      'Sources',
      'TrivialProducer',
      { name: this.state.file.name }
    );
    source.setInputData(ds);

    this.props.proxyManager.createRepresentationInAllViews(source);
    this.props.proxyManager.renderAllViews();
    this.setState({ file: null });
    this.props.updateTab('pipeline');
  }

  updateReader(e) {
    this.setState({ file: null });
  }

  render() {
    return (
      <div className={style.content}>
        <Button onClick={this.loadFile}>
          <Icon type="upload" /> Load local file
        </Button>
        {this.state.file ? (
          <RawReader file={this.state.file} addDataset={this.addDataset} />
        ) : null}
      </div>
    );
  }
}

FileLoader.propTypes = {
  proxyManager: PropTypes.object,
  updateTab: PropTypes.func,
};

FileLoader.defaultProps = {
  proxyManager: null,
  updateTab: () => {},
};
