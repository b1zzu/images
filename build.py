#!/usr/bin/env python3

import argparse
import logging
import subprocess
import uuid
import yaml

logging.basicConfig(format="%(levelname)s: %(message)s", level=logging.DEBUG)


def parser():
    parser = argparse.ArgumentParser(
        description='Build docker image combining multiple templates')
    parser.add_argument(
        '-n',
        '--namespace',
        default=None,
        help='namespace for the docker image')
    parser.add_argument(
        '-v',
        '--version',
        default='alpha',
        help='version to add to the tag for the image')
    parser.add_argument(
        'template',
        metavar='TEMPLATE',
        help='the template to build from templates.yml')
    parser.add_argument(
        'variant',
        metavar='VARIANT',
        help='the variant of the template to build')
    parser.add_argument(
        '-p',
        '--push',
        action='store_true',
        default=False,
        help='push image after building it'
    )
    return parser.parse_args()


arguments = parser()


def exec(*args):
    c = ' '.join(args)
    logging.debug('execute: %s', c)
    subprocess.run(c, shell=True, check=True)


def templates():
    logging.debug('load templates from ./templates.yml')
    f = open('./templates.yml', 'r')
    t = yaml.load(f.read(), Loader=yaml.Loader)
    logging.debug('founded %s templates', len(t))
    return t


templates = templates()


def delete_image(image):
    exec('docker', 'rmi', image)


def tag_image(image, tag):
    exec('docker', 'tag', image, tag)


def push_image(image):
    exec('docker', 'push', image)


def push_images(images):
    for image in images:
        push_image(image)
        logging.info('pushed image %s', image)


def get_info(template, variant):
    if template not in templates:
        logging.error('the template %s does not exists', template)
        exit(1)

    if variant not in templates[template]:
        logging.error('the variant %s %s does not exists', template, variant)
        exit(1)

    return templates[template][variant]


def build_variant_from(template, variant, info, from_image=''):
    logging.debug('building variant %s %s from %s',
                  template, variant, from_image)

    name = template
    template = info.get('template', template)
    version = info.get('version', '')
    image = str(uuid.uuid4())

    exec('docker', 'build',
         '--build-arg', 'FROM_IMAGE={}'.format(from_image),
         '--build-arg', '{}_VERSION={}'.format(name.upper(), version),
         '--tag', image,
         './{}'.format(template))

    return image


def build_variant(template, variant, parents=[]):
    logging.debug('start building variant %s %s', template, variant)

    logging.debug(parents)
    if (template, variant) in parents:
        logging.warning('skip recursion of variant %s %s', template, variant)
        return {}

    parents.append((template, variant))

    info = get_info(template, variant)

    images = {}
    if 'from' in info:
        for from_template, from_variants in info['from'].items():
            for from_variant in from_variants:
                from_images = build_variant(
                    from_template,
                    from_variant,
                    parents.copy())

                for from_tag, from_image in from_images.items():
                    image = build_variant_from(
                        template,
                        variant,
                        info,
                        from_image)
                    delete_image(from_image)
                    tag = '{}-{}{}'.format(from_tag, template, variant)
                    images[tag] = image
    else:
        image = build_variant_from(template, variant, info)
        tag = '{}{}'.format(template, variant)
        images[tag] = image

    return images


namespace = arguments.namespace
namespace = '{}/'.format(namespace) if namespace is not None else ''

version = arguments.version


def build_image(template, variant):
    images = []
    for tag, image in build_variant(template, variant).items():
        tag = '{}{}:{}-{}'.format(namespace, template, version, tag)
        tag_image(image, tag)
        delete_image(image)
        images.append(tag)
        logging.info('built image %s', tag)
    return images


template = arguments.template
variant = arguments.variant

images = build_image(template, variant)
if arguments.push:
    push_image(images)

logging.info('built %s images:', len(images))
for image in images:
    logging.info('  - %s', image)
